"""예상 입·퇴실 시각과 현재 시각으로 입실/퇴실 상태를 맞춘다.

대시보드 ``_effective_check_in_status`` 와 동일 규칙:

- 입실 시각이 없거나 아직 오지 않았으면 → 입실전(pending)
- 퇴실 시각이 지났으면 → 퇴실(checked_out)
- 그 외(입실 시각 <= now) → 입실(checked_in)

앞으로만 진행하지 않고, 입실 시각을 미래로 고친 경우처럼
입실 → 입실전 되돌리기도 수행한다.

DB 반영은 매분 Celery 주기 작업만 담당한다.
"""

from __future__ import annotations

from datetime import datetime

from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from retreat.models import RetreatAttendee, RetreatChangeLog
from retreat.services.audit import log_retreat_change, serialize_model_fields
from retreat.services.lodging_stay import sync_lodging_stay_status
from retreat.services.participation import participating_filter

_AUTO_FIELDS = [
    "check_in_status",
    "check_in_status_manually_set",
    "checked_in_at",
    "checked_out_at",
    "expected_check_in_at",
    "expected_check_out_at",
]

_BATCH_SIZE = 100


def desired_check_in_status(check_in_at, check_out_at, now) -> str:
    """예상 입·퇴실 시각과 현재 시각으로 목표 입·퇴실 상태를 계산한다."""
    S = RetreatAttendee.CheckInStatus
    if check_in_at is None or check_in_at > now:
        return S.PENDING
    if check_out_at is not None and check_out_at <= now:
        return S.CHECKED_OUT
    return S.CHECKED_IN


def _needs_transition_q(now) -> Q:
    """상태 변경 가능성이 있는 행만 골라 불필요한 행 잠금을 피한다."""
    S = RetreatAttendee.CheckInStatus
    to_pending = Q(check_in_status__in=(S.CHECKED_IN, S.CHECKED_OUT)) & (
        Q(expected_check_in_at__isnull=True) | Q(expected_check_in_at__gt=now)
    )
    to_checked_out = (
        Q(expected_check_in_at__isnull=False, expected_check_in_at__lte=now)
        & Q(expected_check_out_at__isnull=False, expected_check_out_at__lte=now)
        & ~Q(check_in_status=S.CHECKED_OUT)
    )
    to_checked_in = (
        Q(expected_check_in_at__isnull=False, expected_check_in_at__lte=now)
        & (Q(expected_check_out_at__isnull=True) | Q(expected_check_out_at__gt=now))
        & ~Q(check_in_status=S.CHECKED_IN)
    )
    automatic = Q(check_in_status_manually_set=False) & (
        to_pending | to_checked_out | to_checked_in
    )
    # 수동 설정 상태는 이전 단계로 되돌리지 않고 다음 단계 도달 시에만 처리한다.
    manual_forward = Q(check_in_status_manually_set=True) & (
        (
            Q(check_in_status=S.PENDING)
            & Q(expected_check_in_at__isnull=False, expected_check_in_at__lte=now)
        )
        | (
            Q(check_in_status=S.CHECKED_IN)
            & Q(expected_check_in_at__isnull=False, expected_check_in_at__lte=now)
            & Q(expected_check_out_at__isnull=False, expected_check_out_at__lte=now)
        )
    )
    return automatic | manual_forward


def _select_for_update_kwargs() -> dict:
    """현재 DB가 지원하는 비대기 행 잠금 옵션을 반환한다."""
    features = connection.features
    kwargs = {}
    if getattr(features, "has_select_for_update_skip_locked", False):
        kwargs["skip_locked"] = True
    if getattr(features, "has_select_for_update_of", False):
        kwargs["of"] = ("self",)
    return kwargs


def _should_apply_status(attendee: RetreatAttendee, desired: str) -> bool:
    if desired == attendee.check_in_status:
        return False
    if not attendee.check_in_status_manually_set:
        return True
    S = RetreatAttendee.CheckInStatus
    rank = {S.PENDING: 0, S.CHECKED_IN: 1, S.CHECKED_OUT: 2}
    return rank[desired] > rank[attendee.check_in_status]


def _apply_status(attendee: RetreatAttendee, *, new_status: str, now) -> None:
    before = serialize_model_fields(attendee, _AUTO_FIELDS)
    S = RetreatAttendee.CheckInStatus
    attendee.check_in_status = new_status
    attendee.check_in_status_manually_set = False
    update_fields = [
        "check_in_status",
        "check_in_status_manually_set",
        "updated_at",
    ]

    if new_status == S.PENDING:
        if attendee.checked_in_at is not None:
            attendee.checked_in_at = None
            update_fields.append("checked_in_at")
        if attendee.checked_out_at is not None:
            attendee.checked_out_at = None
            update_fields.append("checked_out_at")
    elif new_status == S.CHECKED_IN:
        if attendee.checked_in_at is None:
            attendee.checked_in_at = now
            update_fields.append("checked_in_at")
        if attendee.checked_out_at is not None:
            attendee.checked_out_at = None
            update_fields.append("checked_out_at")
    else:  # CHECKED_OUT
        if attendee.checked_in_at is None:
            attendee.checked_in_at = now
            update_fields.append("checked_in_at")
        attendee.checked_out_at = now
        update_fields.append("checked_out_at")

    if sync_lodging_stay_status(attendee):
        update_fields.append("lodging_stay_status")
    attendee.save(update_fields=update_fields)
    log_retreat_change(
        user=None,
        event=attendee.group.event_id,
        action=RetreatChangeLog.Action.UPDATE,
        target_type=RetreatChangeLog.TargetType.ATTENDEE,
        target_id=attendee.id,
        payload_before=before,
        payload_after=serialize_model_fields(attendee, _AUTO_FIELDS),
    )


def apply_due_auto_transitions(
    now: datetime | None = None,
    *,
    event_id: int | None = None,
) -> dict:
    """예상 시각 기준으로 조원 입·퇴실 상태를 동기화한다. 처리 건수를 반환.

    event_id 가 주어지면 해당 집회 조원만 처리한다.
    후보만 잠그고 배치 단위로 짧게 커밋한다.
    """
    now = now or timezone.now()
    S = RetreatAttendee.CheckInStatus
    to_pending = 0
    checked_in = 0
    checked_out = 0

    base = participating_filter(
        RetreatAttendee.objects.filter(_needs_transition_q(now))
    )
    if event_id is not None:
        base = base.filter(group__event_id=event_id)

    candidate_ids = list(base.order_by("pk").values_list("pk", flat=True))
    lock_kwargs = _select_for_update_kwargs()
    for start in range(0, len(candidate_ids), _BATCH_SIZE):
        batch_ids = candidate_ids[start : start + _BATCH_SIZE]
        with transaction.atomic():
            candidates = (
                RetreatAttendee.objects.select_for_update(**lock_kwargs)
                .select_related("group")
                .filter(pk__in=batch_ids)
                .order_by("pk")
            )
            for attendee in candidates:
                desired = desired_check_in_status(
                    attendee.expected_check_in_at,
                    attendee.expected_check_out_at,
                    now,
                )
                if not _should_apply_status(attendee, desired):
                    continue
                _apply_status(attendee, new_status=desired, now=now)
                if desired == S.PENDING:
                    to_pending += 1
                elif desired == S.CHECKED_IN:
                    checked_in += 1
                else:
                    checked_out += 1

    return {
        "pending": to_pending,
        "checked_in": checked_in,
        "checked_out": checked_out,
    }
