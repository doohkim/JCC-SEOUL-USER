"""기준 주일(일요일) 기준 주차 키 — 집계·API 롤업용 (저장 테이블 아님)."""

from __future__ import annotations

from datetime import date, timedelta

from django.http import Http404

from attendance.choices import MidweekServiceType
from attendance.importers.member_resolve import week_sunday_on_or_before
from attendance.models import MidweekAttendanceRecord, SundayAttendanceLine
from users.models import Division

__all__ = [
    "week_sunday_on_or_before",
    "week_sunday_on_or_after",
    "parse_week_rollup_key",
    "distinct_week_sundays_for_division",
    "sunday_lines_for_week",
    "midweek_records_for_week",
    "rollup_row_for_week",
    "sunday_week_index_in_month",
]


def sunday_week_index_in_month(sunday: date) -> int:
    """해당 달에서 기준 일요일이 몇 번째 일요일인지 (1부터). ``sunday`` 는 일요일이어야 함."""
    y, m, dom = sunday.year, sunday.month, sunday.day
    idx = 0
    for day in range(1, dom + 1):
        d = date(y, m, day)
        if d.weekday() == 6:
            idx += 1
    return max(idx, 1)


def week_sunday_on_or_after(d: date) -> date:
    """해당 날짜 기준, 같은 주의(또는 다음) 일요일."""
    return d + timedelta(days=(6 - d.weekday()) % 7)


def parse_week_rollup_key(raw: str) -> date:
    try:
        d = date.fromisoformat(raw)
    except ValueError as e:
        raise Http404("week_sunday은 YYYY-MM-DD 날짜여야 합니다.") from e
    return week_sunday_on_or_after(d)


def distinct_week_sundays_for_division(division: Division) -> list[date]:
    keys: set[date] = set()
    for d in SundayAttendanceLine.objects.filter(division=division).values_list(
        "service_date", flat=True
    ).distinct():
        keys.add(week_sunday_on_or_after(d))
    for d in MidweekAttendanceRecord.objects.filter(division=division).values_list(
        "service_date", flat=True
    ).distinct():
        keys.add(week_sunday_on_or_after(d))
    return sorted(keys, reverse=True)


def sunday_lines_for_week(division: Division, week_sunday: date):
    return SundayAttendanceLine.objects.filter(
        division=division, service_date=week_sunday
    )


def midweek_records_for_week(division: Division, week_sunday: date):
    week_start = week_sunday - timedelta(days=6)
    week_end = week_sunday - timedelta(days=1)
    return MidweekAttendanceRecord.objects.filter(
        division=division,
        service_date__gte=week_start,
        service_date__lte=week_end,
    )


def rollup_row_for_week(division: Division, week_sunday: date) -> dict:
    sun_qs = sunday_lines_for_week(division, week_sunday)
    mw_qs = midweek_records_for_week(division, week_sunday)
    wed_c = mw_qs.filter(service_type=MidweekServiceType.WEDNESDAY).count()
    sat_c = mw_qs.filter(service_type=MidweekServiceType.SATURDAY).count()
    return {
        "week_sunday": week_sunday.isoformat(),
        "division_code": division.code,
        "division_name": division.name,
        "sunday_line_count": sun_qs.count(),
        "midweek_record_count": mw_qs.count(),
        "wednesday_record_count": wed_c,
        "saturday_record_count": sat_c,
        "sunday_week_index_in_month": sunday_week_index_in_month(week_sunday),
    }
