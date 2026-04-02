"""팀 예배 출석부(TeamAttendanceSession) 롤링 7일 보장 — 수동 실행용."""

from django.core.management.base import BaseCommand

from attendance.services.team_attendance_sessions import (
    ensure_team_attendance_sessions_for_rolling_window,
    ensure_team_attendance_sessions_for_anchor_date,
)
from attendance.services.parking import korea_today


class Command(BaseCommand):
    help = (
        "한국 날짜 기준 오늘부터 설정된 롤링 윈도우 내 수·토·주일에 대해 "
        "모든 팀의 TeamAttendanceSession 을 생성(이미 있으면 스킵)합니다."
    )

    def handle(self, *args, **options):
        anchor_date_str = options.get("anchor_date")
        days = options.get("days")
        days_int = int(days) if days is not None else None

        if anchor_date_str:
            from datetime import date

            anchor = date.fromisoformat(anchor_date_str)
            result = ensure_team_attendance_sessions_for_anchor_date(
                anchor, days=days_int
            )
        else:
            if days_int is None:
                result = ensure_team_attendance_sessions_for_rolling_window()
            else:
                result = ensure_team_attendance_sessions_for_anchor_date(
                    korea_today(), days=days_int
                )
        self.stdout.write(str(result))

    def add_arguments(self, parser):
        parser.add_argument(
            "--anchor-date",
            dest="anchor_date",
            required=False,
            help="YYYY-MM-DD. 지정된 날짜를 기준으로 생성합니다.",
        )
        parser.add_argument(
            "--days",
            dest="days",
            required=False,
            help="롤링 윈도우 크기(일). 지정하지 않으면 settings 값(T-3 등)을 사용합니다.",
        )
