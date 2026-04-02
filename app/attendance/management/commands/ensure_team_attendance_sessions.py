"""팀 예배 출석부(TeamAttendanceSession) 롤링 7일 보장 — 수동 실행용."""

from django.core.management.base import BaseCommand

from attendance.services.team_attendance_sessions import (
    ensure_team_attendance_sessions_for_rolling_window,
)


class Command(BaseCommand):
    help = (
        "한국 날짜 기준 오늘부터 7일(오늘~오늘+6) 안의 수·토·주일에 대해 "
        "모든 팀의 TeamAttendanceSession 을 생성(이미 있으면 스킵)합니다."
    )

    def handle(self, *args, **options):
        result = ensure_team_attendance_sessions_for_rolling_window()
        self.stdout.write(str(result))
