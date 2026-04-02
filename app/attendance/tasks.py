"""Celery 작업."""

from __future__ import annotations

from celery import shared_task

from attendance.services.team_attendance_sessions import (
    ensure_team_attendance_sessions_for_rolling_window,
    ensure_team_attendance_sessions_for_anchor_date,
)
from attendance.services.parking import korea_today

@shared_task(name="attendance.tasks.ensure_team_attendance_sessions_next_week")
def ensure_team_attendance_sessions_next_week(anchor_date: str | None = None) -> dict:
    """
    매일 실행: 한국 날짜 기준 오늘부터 설정된 롤링 윈도우(일) 안의 수·토·일마다 팀별 ``TeamAttendanceSession`` 생성.
    """
    if anchor_date:
        anchor = __import__("datetime").date.fromisoformat(anchor_date)
        return ensure_team_attendance_sessions_for_anchor_date(anchor, days=None)
    return ensure_team_attendance_sessions_for_rolling_window()


@shared_task(name="attendance.tasks.ensure_team_attendance_sessions_next_7_days")
def ensure_team_attendance_sessions_next_7_days(anchor_date: str | None = None) -> dict:
    """
    사용자가 “next_7_days” 이름으로 직접 실행하던 기존 관례를 유지하기 위한 alias 태스크.

    - `anchor_date`(YYYY-MM-DD)를 주면 그 기준일로 anchor~anchor+(7-1) 동안 생성
    - 없으면 korea_today() 기준으로 생성
    """
    if anchor_date:
        anchor = __import__("datetime").date.fromisoformat(anchor_date)
        return ensure_team_attendance_sessions_for_anchor_date(anchor, days=7)
    return ensure_team_attendance_sessions_for_anchor_date(korea_today(), days=7)


@shared_task(name="attendance.tasks.ensure_team_attendance_sessions_next_3_days")
def ensure_team_attendance_sessions_next_3_days(anchor_date: str | None = None) -> dict:
    """
    주기 배치에서 호출하는 태스크.

    중요:
    태스크 함수명이 next_3_days여도, 실제 생성 범위는 `settings.TEAM_ATTENDANCE_SESSION_ROLLING_DAYS`
    값에 의해 결정된다(앞으로 migrations 없이 롤링 기간만 바꾸기 위함).
    """
    if anchor_date:
        anchor = __import__("datetime").date.fromisoformat(anchor_date)
        return ensure_team_attendance_sessions_for_anchor_date(anchor, days=None)
    return ensure_team_attendance_sessions_for_rolling_window()
