"""팀 단위 예배 출석부(TeamAttendanceSession) 자동 생성."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from attendance.models import TeamAttendanceSession
from attendance.services.parking import korea_today
from users.models import Team

logger = logging.getLogger(__name__)

# Python weekday: 월=0 … 일=6 → 수=2, 토=5, 일=6
_WORSHIP_WEEKDAYS = frozenset({2, 5, 6})


def worship_service_dates_in_seven_day_window(anchor: dt.date) -> list[dt.date]:
    """앵커 날짜 포함 7일(앵커 ~ 앵커+6) 안에서 수·토·주일 예배일만."""
    out: list[dt.date] = []
    for i in range(7):
        d = anchor + dt.timedelta(days=i)
        if d.weekday() in _WORSHIP_WEEKDAYS:
            out.append(d)
    return out


def ensure_team_attendance_sessions_for_rolling_window() -> dict[str, Any]:
    """
    한국 달력 기준 '오늘'부터 7일치(오늘~오늘+6) 범위에서
    수·토·주일에 해당하는 날짜마다 모든 팀에 대해 TeamAttendanceSession 을 보장한다.
    이미 있으면 건너뛴다(get_or_create / bulk ignore).
    """
    today = korea_today()
    dates = worship_service_dates_in_seven_day_window(today)
    teams = list(Team.objects.select_related("division").order_by("division_id", "id"))
    if not dates:
        return {
            "today": today.isoformat(),
            "service_dates": [],
            "team_count": len(teams),
            "candidates": 0,
            "note": "no_worship_days_in_window",
        }

    to_create: list[TeamAttendanceSession] = []
    for team in teams:
        for d in dates:
            to_create.append(
                TeamAttendanceSession(
                    team_id=team.id,
                    session_date=d,
                    period_count=3,
                    title="",
                    period_labels=[],
                    notes="",
                )
            )

    # 동일 (team, session_date) 는 DB 유니크 → 중복은 무시
    TeamAttendanceSession.objects.bulk_create(to_create, ignore_conflicts=True)

    logger.info(
        "team_attendance_sessions_ensure: today=%s dates=%s teams=%s candidates=%s",
        today.isoformat(),
        [x.isoformat() for x in dates],
        len(teams),
        len(to_create),
    )

    return {
        "today": today.isoformat(),
        "service_dates": [x.isoformat() for x in dates],
        "team_count": len(teams),
        "candidates": len(to_create),
    }
