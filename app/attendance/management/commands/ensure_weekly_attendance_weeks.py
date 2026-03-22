"""
부서별 **주간 출석부(주차)** ``AttendanceWeek`` 행을 미리 만듭니다.

- ``week_sunday``: 오늘(한국 날짜)이 속한 주의 **주일**부터, 연속 N주의 주일 날짜로 주차를 식별합니다.
- 수·토·주일 **개별 출석 행**은 만들지 않고, 주차 껍데기만 ``get_or_create`` 합니다.

크론 예시 (매주 월요일 09:00 KST)::

    0 9 * * 1 cd /path/to/app && /path/to/python manage.py ensure_weekly_attendance_weeks --weeks 8

사용::

    python manage.py ensure_weekly_attendance_weeks
    python manage.py ensure_weekly_attendance_weeks --weeks 12 --division-code youth
    python manage.py ensure_weekly_attendance_weeks --all-divisions
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction

from attendance.models import AttendanceWeek
from users.models import Division


def _sunday_on_or_before(d: dt.date) -> dt.date:
    """월=0 … 일=6 기준, d가 속한 주의 일요일(당일이 일요일이면 d)."""
    delta = (d.weekday() + 1) % 7
    return d - dt.timedelta(days=delta)


def _iter_week_sundays(*, count: int, tz_name: str) -> list[dt.date]:
    today = dt.datetime.now(ZoneInfo(tz_name)).date()
    first = _sunday_on_or_before(today)
    return [first + dt.timedelta(weeks=i) for i in range(count)]


class Command(BaseCommand):
    help = "주간 출석부 AttendanceWeek 를 앞으로 N주치 자동 생성(get_or_create)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--weeks",
            type=int,
            default=8,
            help="생성할 주 수 (기본 8)",
        )
        parser.add_argument(
            "--division-code",
            action="append",
            default=[],
            help="부서 code (여러 번 지정 가능). 미지정이면 youth 만",
        )
        parser.add_argument(
            "--all-divisions",
            action="store_true",
            help="등록된 모든 Division 에 대해 생성",
        )
        parser.add_argument(
            "--timezone",
            default="Asia/Seoul",
            help="오늘 날짜 판별용 타임존 (기본 Asia/Seoul)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="DB에 쓰지 않고 만들 주일 목록만 출력",
        )

    def handle(self, *args, **options):
        weeks_n = max(1, options["weeks"])
        tz_name = options["timezone"]
        sundays = _iter_week_sundays(count=weeks_n, tz_name=tz_name)

        if options["all_divisions"]:
            divisions = list(Division.objects.order_by("sort_order", "name"))
        elif options["division_code"]:
            codes = options["division_code"]
            divisions = list(Division.objects.filter(code__in=codes))
            missing = set(codes) - {d.code for d in divisions}
            if missing:
                self.stdout.write(self.style.WARNING(f"없는 division code: {missing}"))
        else:
            divisions = list(Division.objects.filter(code="youth"))
            if not divisions:
                self.stdout.write(
                    self.style.WARNING(
                        "code=youth 인 부서가 없습니다. "
                        "--division-code 또는 --all-divisions 를 사용하세요."
                    )
                )

        if options["dry_run"]:
            self.stdout.write(f"타임존 {tz_name}, 주일 목록: {sundays}")
            for d in divisions:
                self.stdout.write(f"  [dry] division={d.code} → {len(sundays)}주")
            return

        created = 0
        existing = 0
        with transaction.atomic():
            for div in divisions:
                for sun in sundays:
                    _, was_created = AttendanceWeek.objects.get_or_create(
                        division=div,
                        week_sunday=sun,
                        defaults={"auto_created": True},
                    )
                    if was_created:
                        created += 1
                    else:
                        existing += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"완료: 신규 주차 {created}건, 이미 있음 {existing}건 "
                f"(부서 {len(divisions)}개 × 최대 {weeks_n}주)"
            )
        )
