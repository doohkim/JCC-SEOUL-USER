"""예상 입·퇴실 시각이 지나면 자동으로 입실/퇴실 상태로 전환한다.

- 입실전(pending) & 예상 입실시각 <= now  →  입실(checked_in) + 실제 입실시각 기록
- 입실(checked_in) & 예상 퇴실시각 <= now  →  퇴실(checked_out) + 실제 퇴실시각 기록

매분 Celery 주기 작업에서 호출한다. 이미 더 진행된 상태(수동 처리 포함)는 건드리지 않는다.
"""

from __future__ import annotations

from datetime import datetime

from django.db import transaction
from django.utils import timezone

from retreat.models import RetreatAttendee, RetreatChangeLog
from retreat.services.audit import log_retreat_change, serialize_model_fields

_AUTO_FIELDS = [
    "check_in_status",
    "checked_in_at",
    "checked_out_at",
    "expected_check_in_at",
    "expected_check_out_at",
]


def _transition(attendee: RetreatAttendee, *, new_status: str, stamp_field: str, now):
    before = serialize_model_fields(attendee, _AUTO_FIELDS)
    attendee.check_in_status = new_status
    setattr(attendee, stamp_field, now)
    attendee.save(update_fields=["check_in_status", stamp_field, "updated_at"])
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
    """예상 시각이 지난 조원을 입실/퇴실로 자동 전환한다. 처리 건수를 반환.

    event_id 가 주어지면 해당 행사 조원만 처리한다(대시보드·조 관리 온디맨드).
    생략하면 전체 행사 대상(Celery 매분 작업).
    """
    now = now or timezone.now()
    checked_in = 0
    checked_out = 0

    # 1) 입실전 & 예상 입실시각 경과 → 입실
    pending_due = (
        RetreatAttendee.objects.select_for_update()
        .select_related("group")
        .filter(
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
            expected_check_in_at__isnull=False,
            expected_check_in_at__lte=now,
        )
    )
    if event_id is not None:
        pending_due = pending_due.filter(group__event_id=event_id)
    for attendee in pending_due:
        _transition(
            attendee,
            new_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
            stamp_field="checked_in_at",
            now=now,
        )
        checked_in += 1

    # 2) 입실 & 예상 퇴실시각 경과 → 퇴실 (방금 자동 입실된 건 포함)
    in_due = (
        RetreatAttendee.objects.select_for_update()
        .select_related("group")
        .filter(
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
            expected_check_out_at__isnull=False,
            expected_check_out_at__lte=now,
        )
    )
    if event_id is not None:
        in_due = in_due.filter(group__event_id=event_id)
    for attendee in in_due:
        _transition(
            attendee,
            new_status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
            stamp_field="checked_out_at",
            now=now,
        )
        checked_out += 1

    return {"checked_in": checked_in, "checked_out": checked_out}
