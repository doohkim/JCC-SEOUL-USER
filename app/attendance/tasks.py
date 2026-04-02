"""Celery 작업."""

from __future__ import annotations

from celery import shared_task

from attendance.services.team_attendance_sessions import (
    ensure_team_attendance_sessions_for_rolling_window,
)


@shared_task(name="attendance.tasks.ensure_team_attendance_sessions_next_week")
def ensure_team_attendance_sessions_next_week() -> dict:
    """매일 실행: 오늘 기준 7일(오늘~+6) 내 수·토·주일 팀 출석부 자동 생성."""
    return ensure_team_attendance_sessions_for_rolling_window()
