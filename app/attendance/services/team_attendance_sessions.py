"""팀 단위 예배 출석부(TeamAttendanceSession) 자동 생성.

역할 요약
---------
- **TeamAttendanceSession**(팀 × 예배일): 예배 회차(출석부 슬롯) 마스터. 매일 배치로 미리 깔아 두면
  주차·Admin(교시 칩) 등에서 “이 날짜에 회차가 있다”는 전제를 둘 수 있다.
- 팀장 웹 출석(`team_roster_check`)에서 저장되는 데이터는 **SundayAttendanceLine** /
  **MidweekAttendanceRecord**이며, 부서 대시보드 집계(`build_week_summary_payload`)도
  이 테이블을 읽는다. 회차 레코드와 같은 날짜·부서로 맞물리지만, ORM FK로 묶이지는 않는다.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from django.conf import settings

from attendance.models import TeamAttendanceSession
from attendance.services.parking import korea_today
from users.models import Team

logger = logging.getLogger(__name__)

# Python weekday: 월=0 … 일=6 → 수=2, 토=5, 일=6
_WORSHIP_WEEKDAYS = frozenset({2, 5, 6})

def _rolling_days_default() -> int:
    return int(getattr(settings, "TEAM_ATTENDANCE_SESSION_ROLLING_DAYS", 3))


def worship_service_dates_in_rolling_window(
    anchor: dt.date, *, days: int
) -> list[dt.date]:
    """앵커 포함 ``days``일(앵커 ~ 앵커+days-1) 안의 수·토·일 예배일만 오름차순."""
    out: list[dt.date] = []
    n = max(1, min(int(days), 62))
    for i in range(n):
        d = anchor + dt.timedelta(days=i)
        if d.weekday() in _WORSHIP_WEEKDAYS:
            out.append(d)
    return out


def worship_service_dates_in_seven_day_window(anchor: dt.date) -> list[dt.date]:
    """하위 호환: 예전 7일 윈도우와 동일."""
    return worship_service_dates_in_rolling_window(anchor, days=7)


def ensure_team_attendance_sessions_for_rolling_window() -> dict[str, Any]:
    """한국 날짜 기준 **오늘**부터 설정된 롤링 윈도우(일) 내 예배일마다 세션을 보장."""
    anchor = korea_today()
    return ensure_team_attendance_sessions_for_anchor_date(anchor, days=None)


def ensure_team_attendance_sessions_for_anchor_date(
    anchor: dt.date,
    *,
    days: int | None,
) -> dict[str, Any]:
    """기준일(`anchor`)부터 `days` 동안의 수·토·주일 예배일마다 세션을 보장."""
    rolling_days = int(_rolling_days_default()) if days is None else int(days)
    dates = worship_service_dates_in_rolling_window(anchor, days=rolling_days)
    teams = list(Team.objects.select_related("division").order_by("division_id", "id"))
    if not dates:
        return {
            "anchor": anchor.isoformat(),
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
        "team_attendance_sessions_ensure: anchor=%s dates=%s teams=%s candidates=%s",
        anchor.isoformat(),
        [x.isoformat() for x in dates],
        len(teams),
        len(to_create),
    )

    return {
        "anchor": anchor.isoformat(),
        "service_dates": [x.isoformat() for x in dates],
        "team_count": len(teams),
        "candidates": len(to_create),
    }
