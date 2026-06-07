"""조원 입·퇴실 시각 자동/수동 기록."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.utils import timezone

from retreat.models import RetreatAttendee


def ensure_stamps_for_status(
    attendee: RetreatAttendee, *, now: datetime | None = None
) -> None:
    """상태와 실제 시각 필드가 어긋나면 보정한다 (레거시·직접 DB 수정 대비)."""
    ts = now or timezone.now()
    S = RetreatAttendee.CheckInStatus
    if attendee.check_in_status in (S.CHECKED_IN, S.CHECKED_OUT):
        if not attendee.checked_in_at:
            attendee.checked_in_at = attendee.expected_check_in_at or ts
    if attendee.check_in_status == S.CHECKED_OUT:
        if not attendee.checked_out_at:
            attendee.checked_out_at = attendee.expected_check_out_at or ts


def backfill_missing_check_in_stamps(
    group_ids: list[int] | None = None,
) -> dict[str, int]:
    """입·퇴실 상태인데 실제 시각이 비어 있는 레코드를 보정한다."""
    qs = RetreatAttendee.objects.all()
    if group_ids is not None:
        qs = qs.filter(group_id__in=group_ids)

    filled_in = 0
    filled_out = 0
    S = RetreatAttendee.CheckInStatus

    for attendee in qs.filter(
        check_in_status__in=(S.CHECKED_IN, S.CHECKED_OUT),
        checked_in_at__isnull=True,
    ):
        ensure_stamps_for_status(attendee)
        attendee.save(update_fields=["checked_in_at", "updated_at"])
        filled_in += 1

    for attendee in qs.filter(
        check_in_status=S.CHECKED_OUT,
        checked_out_at__isnull=True,
    ):
        ensure_stamps_for_status(attendee)
        attendee.save(update_fields=["checked_out_at", "updated_at"])
        filled_out += 1

    return {"filled_checked_in_at": filled_in, "filled_checked_out_at": filled_out}


def stamp_check_in_status(
    attendee: RetreatAttendee,
    *,
    previous_status: str,
    new_status: str,
    manual_checked_in_at: datetime | None = None,
    manual_checked_out_at: datetime | None = None,
    now: datetime | None = None,
) -> None:
    """check_in_status 변경 또는 관리자 수동 시각 입력을 반영한다.

  - manual_* 가 주어지면 해당 필드만 설정(시간 수정).
  - 상태가 바뀌면 now() 로 해당 시각 필드를 갱신한다.
    """
    if manual_checked_in_at is not None:
        attendee.checked_in_at = manual_checked_in_at
    if manual_checked_out_at is not None:
        attendee.checked_out_at = manual_checked_out_at

    if previous_status == new_status and (
        manual_checked_in_at is None and manual_checked_out_at is None
    ):
        return

    ts = now or timezone.now()
    if previous_status != new_status:
        if new_status == RetreatAttendee.CheckInStatus.CHECKED_IN:
            attendee.checked_in_at = ts
        elif new_status == RetreatAttendee.CheckInStatus.CHECKED_OUT:
            attendee.checked_out_at = ts

    ensure_stamps_for_status(attendee, now=ts)


def apply_attendee_stamp_from_payload(
    attendee: RetreatAttendee,
    *,
    previous_status: str,
    validated_data: dict[str, Any],
    manual_checked_in_at: datetime | None,
    manual_checked_out_at: datetime | None,
) -> None:
    """serializer.save() 전에 시각 필드를 미리 반영."""
    new_status = validated_data.get("check_in_status", previous_status)
    stamp_check_in_status(
        attendee,
        previous_status=previous_status,
        new_status=new_status,
        manual_checked_in_at=manual_checked_in_at,
        manual_checked_out_at=manual_checked_out_at,
    )
