"""슬롯 생성·상담 신청 상태 전이."""

from __future__ import annotations

import datetime as dt
import uuid
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from counseling.models import (
    CounselorDayOverride,
    CounselorScheduleSettings,
    CounselingRequest,
    CounselingSlot,
)


def _tz() -> ZoneInfo:
    name = getattr(settings, "COUNSELING_TIMEZONE", "Asia/Seoul")
    return ZoneInfo(name)


def today_in_counseling_tz() -> dt.date:
    return dt.datetime.now(tz=_tz()).date()


def horizon_last_date() -> dt.date:
    offset = int(getattr(settings, "COUNSELING_HORIZON_DAY_OFFSET", 7))
    return today_in_counseling_tz() + dt.timedelta(days=offset)


def date_range_horizon() -> tuple[dt.date, dt.date]:
    start = today_in_counseling_tz()
    end = horizon_last_date()
    return start, end


def iter_dates_in_horizon() -> list[dt.date]:
    start, end = date_range_horizon()
    out: list[dt.date] = []
    d = start
    while d <= end:
        out.append(d)
        d += dt.timedelta(days=1)
    return out


def get_or_create_schedule_settings(counselor_id: int) -> CounselorScheduleSettings:
    obj, _ = CounselorScheduleSettings.objects.get_or_create(
        user_id=counselor_id,
        defaults={
            "slot_duration_minutes": 60,
            "default_start_hour": 10,
            "default_end_hour": 23,
        },
    )
    return obj


def _hours_for_weekday(settings_obj: CounselorScheduleSettings, weekday: int) -> tuple[int, int]:
    raw = settings_obj.weekday_hours_json
    if isinstance(raw, dict) and str(weekday) in raw:
        block = raw[str(weekday)]
        if isinstance(block, dict) and "start" in block and "end" in block:
            return int(block["start"]), int(block["end"])
    return settings_obj.default_start_hour, settings_obj.default_end_hour


def _desired_ranges_for_day(
    counselor_id: int,
    day: dt.date,
    settings_obj: CounselorScheduleSettings,
) -> list[tuple[dt.time, dt.time]]:
    override = (
        CounselorDayOverride.objects.filter(counselor_id=counselor_id, date=day).first()
    )
    if override and override.is_closed:
        return []

    duration = settings_obj.slot_duration_minutes

    if override and override.custom_slots_json is not None:
        return _parse_custom_slots(override.custom_slots_json, duration)

    start_h, end_h = _hours_for_weekday(settings_obj, day.weekday())
    return _ranges_from_hours(start_h, end_h, duration)


def _parse_custom_slots(data, duration_minutes: int) -> list[tuple[dt.time, dt.time]]:
    if isinstance(data, list) and data and isinstance(data[0], int):
        out: list[tuple[dt.time, dt.time]] = []
        for h in sorted({int(x) for x in data}):
            st = dt.time(h, 0)
            et = (dt.datetime.combine(dt.date.min, st) + dt.timedelta(minutes=duration_minutes)).time()
            out.append((st, et))
        return out

    if isinstance(data, list) and data and isinstance(data[0], (list, tuple)):
        out: list[tuple[dt.time, dt.time]] = []
        for pair in data:
            if len(pair) != 2:
                continue
            a, b = str(pair[0]), str(pair[1])
            sh, sm = map(int, a.split(":"))
            eh, em = map(int, b.split(":"))
            st = dt.time(sh, sm)
            et = dt.time(eh, em)
            out.append((st, et))
        return out

    return []


def _ranges_from_hours(start_h: int, end_h: int, duration_minutes: int) -> list[tuple[dt.time, dt.time]]:
    """end_h: 마지막 슬롯 종료 시각(시). 예: 23이면 22:00~23:00 슬롯까지."""
    out: list[tuple[dt.time, dt.time]] = []
    start_min = start_h * 60
    end_boundary = end_h * 60
    cur = start_min
    while cur + duration_minutes <= end_boundary:
        st = dt.time(cur // 60, cur % 60)
        et = (dt.datetime.combine(dt.date.min, st) + dt.timedelta(minutes=duration_minutes)).time()
        out.append((st, et))
        cur += duration_minutes
    return out


def ensure_slots_for_horizon(counselor_id: int) -> None:
    """롤링 창 날짜에 맞게 OPEN 슬롯을 idempotent하게 맞춘다."""
    settings_obj = get_or_create_schedule_settings(counselor_id)
    for day in iter_dates_in_horizon():
        desired = _desired_ranges_for_day(counselor_id, day, settings_obj)
        desired_pairs = {(a, b) for a, b in desired}

        existing = CounselingSlot.objects.filter(counselor_id=counselor_id, date=day)
        for slot in existing:
            key = (slot.start_time, slot.end_time)
            if slot.state == CounselingSlot.State.OPEN and key not in desired_pairs:
                slot.delete()

        for st, et in desired:
            if CounselingSlot.objects.filter(
                counselor_id=counselor_id,
                date=day,
                start_time=st,
            ).exists():
                continue
            CounselingSlot.objects.create(
                counselor_id=counselor_id,
                date=day,
                start_time=st,
                end_time=et,
                state=CounselingSlot.State.OPEN,
            )


def create_counseling_request(*, applicant_id: int, slot_id: int, message: str) -> CounselingRequest:
    with transaction.atomic():
        slot = CounselingSlot.objects.select_for_update().get(pk=slot_id)
        if slot.counselor_id == applicant_id:
            raise ValueError("본인에게는 상담을 신청할 수 없습니다.")
        if slot.state != CounselingSlot.State.OPEN:
            raise ValueError("이미 신청되었거나 예약할 수 없는 시간입니다.")

        req = CounselingRequest.objects.create(
            applicant_id=applicant_id,
            counselor_id=slot.counselor_id,
            slot=slot,
            status=CounselingRequest.Status.PENDING,
            applicant_message=message or "",
        )
        slot.state = CounselingSlot.State.PENDING
        slot.save(update_fields=["state", "updated_at"])
        return req


def accept_counseling_request(*, user_id: int, req: CounselingRequest) -> CounselingRequest:
    if req.counselor_id != user_id:
        raise PermissionError
    with transaction.atomic():
        locked = CounselingRequest.objects.select_for_update().select_related("slot").get(pk=req.pk)
        if locked.status != CounselingRequest.Status.PENDING:
            raise ValueError("처리할 수 없는 상태입니다.")
        locked.status = CounselingRequest.Status.ACCEPTED
        locked.slot.state = CounselingSlot.State.BOOKED
        locked.slot.save(update_fields=["state", "updated_at"])
        locked.save(update_fields=["status", "updated_at"])
        return locked


def reject_counseling_request(*, user_id: int, req: CounselingRequest) -> CounselingRequest:
    if req.counselor_id != user_id:
        raise PermissionError
    with transaction.atomic():
        locked = CounselingRequest.objects.select_for_update().select_related("slot").get(pk=req.pk)
        if locked.status != CounselingRequest.Status.PENDING:
            raise ValueError("처리할 수 없는 상태입니다.")
        locked.status = CounselingRequest.Status.REJECTED
        locked.slot.state = CounselingSlot.State.OPEN
        locked.slot.save(update_fields=["state", "updated_at"])
        locked.save(update_fields=["status", "updated_at"])
        return locked


def cancel_counseling_request(*, user_id: int, req: CounselingRequest) -> CounselingRequest:
    if req.applicant_id != user_id:
        raise PermissionError
    with transaction.atomic():
        locked = CounselingRequest.objects.select_for_update().select_related("slot").get(pk=req.pk)
        if locked.status != CounselingRequest.Status.PENDING:
            raise ValueError("취소할 수 없는 상태입니다.")
        locked.status = CounselingRequest.Status.CANCELLED
        locked.slot.state = CounselingSlot.State.OPEN
        locked.slot.save(update_fields=["state", "updated_at"])
        locked.save(update_fields=["status", "updated_at"])
        return locked


def counseling_request_detail_for_user(*, user, public_id):
    if isinstance(public_id, str):
        public_id = uuid.UUID(public_id)
    qs = CounselingRequest.objects.select_related("slot", "applicant", "counselor")
    q_filter = Q(public_id=public_id) & (
        Q(applicant_id=user.pk) | Q(counselor_id=user.pk)
    )
    return get_object_or_404(qs.filter(q_filter))
