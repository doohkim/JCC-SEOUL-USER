"""예상 입·퇴실 시각과 현재 시각으로 입실/퇴실 상태를 맞춘다.

대시보드 ``_effective_check_in_status`` 와 동일 규칙:

- 입실 시각이 없거나 아직 오지 않았으면 → 입실전(pending)
- 퇴실 시각이 지났으면 → 퇴실(checked_out)
- 그 외(입실 시각 <= now) → 입실(checked_in)

앞으로만 진행하지 않고, 입실 시각을 미래로 고친 경우처럼
입실 → 입실전 되돌리기도 수행한다.

매분 Celery 주기 작업·대시보드/조 관리 온디맨드에서 호출한다.
"""

from __future__ import annotations

from datetime import datetime

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from retreat.models import RetreatAttendee, RetreatChangeLog
from retreat.services.audit import log_retreat_change, serialize_model_fields
from retreat.services.lodging_stay import sync_lodging_stay_status
from retreat.services.participation import participating_filter

_AUTO_FIELDS = [
    "check_in_status",
    "checked_in_at",
    "checked_out_at",
    "expected_check_in_at",
    "expected_check_out_at",
]


def desired_check_in_status(check_in_at, check_out_at, now) -> str:
    """예상 입·퇴실 시각과 현재 시각으로 목표 입·퇴실 상태를 계산한다."""
    S = RetreatAttendee.CheckInStatus
    if check_in_at is None or check_in_at > now:
        return S.PENDING
    if check_out_at is not None and check_out_at <= now:
        return S.CHECKED_OUT
    return S.CHECKED_IN


def _apply_status(attendee: RetreatAttendee, *, new_status: str, now) -> None:
    before = serialize_model_fields(attendee, _AUTO_FIELDS)
    S = RetreatAttendee.CheckInStatus
    attendee.check_in_status = new_status
    update_fields = ["check_in_status", "updated_at"]

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


@transaction.atomic
def apply_due_auto_transitions(
    now: datetime | None = None,
    *,
    event_id: int | None = None,
) -> dict:
    """예상 시각 기준으로 조원 입·퇴실 상태를 동기화한다. 처리 건수를 반환.

    event_id 가 주어지면 해당 집회 조원만 처리한다(대시보드·조 관리 온디맨드).
    생략하면 전체 집회 대상(Celery 매분 작업).
    """
    now = now or timezone.now()
    S = RetreatAttendee.CheckInStatus
    to_pending = 0
    checked_in = 0
    checked_out = 0

    # 입실전이면서 예상 입실이 없는 행은 이미 목표 상태이므로 제외.
    candidates = participating_filter(
        RetreatAttendee.objects.select_for_update()
        .select_related("group")
        .filter(
            Q(expected_check_in_at__isnull=False)
            | Q(check_in_status__in=(S.CHECKED_IN, S.CHECKED_OUT))
        )
    )
    if event_id is not None:
        candidates = candidates.filter(group__event_id=event_id)

    for attendee in candidates:
        desired = desired_check_in_status(
            attendee.expected_check_in_at,
            attendee.expected_check_out_at,
            now,
        )
        if desired == attendee.check_in_status:
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
