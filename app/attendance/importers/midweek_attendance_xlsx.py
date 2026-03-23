"""
수요·토요예배 참석자 명단 시트 파싱.

열 구조: 팀 헤더 행에서 ``부서 회장단`` 다음 ``OO팀`` 이 열 번호 ``name_col + 2`` 에 오고,
데이터는 ``name_col`` (1, 3, 5, …) 에 이름, 바로 오른쪽 ``name_col + 1`` 에 **현장** 마킹(v, 온 등).

기본: 이름 옆 **현장** 열에 v/온 등 표시가 있으면 해당 상태로 저장하고, 비어 있으면 **불참(absent)**.
``lenient_empty_venue=True`` 이면 구 스펙처럼 빈 칸도 참석으로 본다.

시트 탭 날짜와 셀 제목 날짜가 다를 때는 **수요/토요가 들어간 제목 셀의 YYYY.MM.DD** 를 우선한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from attendance.choices import MidweekAttendanceStatus
from attendance.importers.sunday_attendance_xlsx import (
    DATE_IN_TITLE_RE,
    _find_header_row_index,
    _find_subheader_row_index,
    parse_title_date,
)

SHEET_DATE_HEAD_RE = re.compile(r"^(\d{2})\.(\d{1,2})\.(\d{1,2})")

MIDWEEK_SKIP_NAMES = frozenset(
    {"회장단", "간사단", "현장", "인천", "부서", "부서회장단"}
)


@dataclass(frozen=True)
class ParsedMidweekAttendanceRow:
    display_name: str
    team_header: str
    status: str


def _midweek_display_name(cell: Any) -> str | None:
    if cell is None or not isinstance(cell, str):
        return None
    s = cell.strip()
    if not s or len(s) < 2:
        return None
    t = s.replace(" ", "")
    if t in MIDWEEK_SKIP_NAMES:
        return None
    if "참석자명단" in t or "참석자 명단" in s:
        return None
    if "예배" in s and "명단" in s:
        return None
    if any(k in s for k in ("합계", "※", "작성")):
        return None
    return s


def _midweek_team_columns(header: tuple) -> list[tuple[int, str]]:
    """
    (이름 열 인덱스, 팀 헤더 문자열).

    시트는 팀마다 블록 너비가 조금씩 달라질 수 있어, ``OO팀``/``부서 회장단`` 열을 직접 찾고
    그보다 **왼쪽 두 칸**을 이름 열로 본다 (이름 | 현장 | … | 팀헤더).
    """
    out: list[tuple[int, str]] = []
    if not header:
        return out
    for team_idx, cell in enumerate(header):
        if not isinstance(cell, str):
            continue
        raw_header = cell.strip()
        compact = raw_header.replace(" ", "")
        if not compact or ("팀" not in compact and "회장단" not in compact):
            continue

        # 일반 팀 블록은 "OO팀" 헤더가 name_col + 2 위치에 있는 구조로 가정한다.
        name_col = team_idx - 2

        # 다만 첫 헤더 "부서 회장단"은 시트에서 name_col + 2 정렬이 깨져있어서,
        # name_col 계산이 음수가 될 수 있다. 이 경우 name_col을 team_idx로 보정한다.
        if compact == "부서회장단":
            # "부서 회장단" 헤더가 시트에서 한 칸씩 어긋나 있는 경우가 있어,
            # 테스트/실데이터 기준으로 name_col을 (team_idx - 2)로 맞춘다.
            name_col = max(team_idx - 2, 0)

        if name_col < 0:
            continue

        # 스냅샷: 부서 회장단은 공백 제거 표준화, 그 외는 엑셀 원문 그대로(공백 포함)
        out.append((name_col, "부서회장단" if compact == "부서회장단" else raw_header))
    return out


def midweek_status_from_venue_cell(cell: Any) -> str | None:
    """현장 열 값 → ``MidweekAttendanceStatus``. 비어 있거나 해석 불가면 None."""
    if cell is None or cell == "":
        return None
    if isinstance(cell, bool):
        return None
    if isinstance(cell, (int, float)):
        if cell in (1, 1.0):
            return MidweekAttendanceStatus.PRESENT
        return None
    s = str(cell).strip()
    if not s or s in ("-", "—"):
        return None
    sl = s.lower()
    if sl in ("v", "✓", "√", "o", "○", "●"):
        return MidweekAttendanceStatus.PRESENT
    if "온" in s:
        return MidweekAttendanceStatus.ONLINE
    if s in ("지",) or "지각" in s:
        return MidweekAttendanceStatus.PRESENT
    if sl in ("x", "absent"):
        return MidweekAttendanceStatus.ABSENT
    return None


def parse_midweek_service_date(rows: list[tuple], sheet_name: str = "") -> date | None:
    """수요·토요 제목 셀(셀에 수요 또는 토요 포함)의 날짜 → 시트 상단 임의 날짜 → 시트 탭."""
    for row in rows[:30]:
        for cell in row:
            if not isinstance(cell, str):
                continue
            if "수요" not in cell and "토요" not in cell:
                continue
            m = DATE_IN_TITLE_RE.search(cell)
            if m:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                try:
                    return date(y, mo, d)
                except ValueError:
                    continue
    fb = parse_title_date(rows)
    if fb:
        return fb
    return parse_date_from_sheet_name(sheet_name) if sheet_name else None


def parse_date_from_sheet_name(sheet_name: str) -> date | None:
    """``26.03.25 수요예배`` 처럼 시트명 앞의 ``YY.MM.DD``."""
    m = SHEET_DATE_HEAD_RE.match(sheet_name.strip())
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    full_y = 2000 + y if y < 100 else y
    try:
        return date(full_y, mo, d)
    except ValueError:
        return None


def parse_midweek_attendance_sheet(
    rows: list[tuple],
    *,
    sheet_name: str = "",
    lenient_empty_venue: bool = False,
) -> tuple[date | None, list[ParsedMidweekAttendanceRow]]:
    service_date = parse_midweek_service_date(rows, sheet_name)

    hi = _find_header_row_index(rows)
    if hi is None:
        raise ValueError("시트에서 '부서 회장단' 이 있는 헤더 행을 찾지 못했습니다.")
    teams = _midweek_team_columns(rows[hi])
    if not teams:
        raise ValueError("팀 열(OO팀)을 찾지 못했습니다.")

    sub_i = _find_subheader_row_index(rows, hi)
    if sub_i is None:
        raise ValueError("'현장' 서브헤더 행을 찾지 못했습니다.")

    data_begin = sub_i + 1
    out: list[ParsedMidweekAttendanceRow] = []

    for i in range(data_begin, len(rows)):
        row = rows[i]
        if not row:
            continue
        first_txt = next(
            (str(x).strip() for x in row if isinstance(x, str) and str(x).strip()), ""
        )
        if first_txt and any(
            k in first_txt
            for k in ("합계", "참석자 명단 전체", "작성", "※")
        ):
            continue

        for name_col, team_header in teams:
            if name_col >= len(row):
                continue
            raw_name = _midweek_display_name(row[name_col])
            if not raw_name:
                continue
            venue_col = name_col + 1
            venue_cell = row[venue_col] if venue_col < len(row) else None
            st = midweek_status_from_venue_cell(venue_cell)
            if st is None:
                st = (
                    MidweekAttendanceStatus.PRESENT
                    if lenient_empty_venue
                    else MidweekAttendanceStatus.ABSENT
                )
            out.append(
                ParsedMidweekAttendanceRow(
                    display_name=raw_name,
                    team_header=team_header,
                    status=st,
                )
            )

    return service_date, out


def dedupe_midweek_by_member(
    parsed: list[ParsedMidweekAttendanceRow],
) -> tuple[list[ParsedMidweekAttendanceRow], int]:
    """같은 사람이 여러 팀 열에 나오면 한 건만 남긴다. 참석·온라인이 불참보다 우선."""
    from attendance.importers.member_resolve import member_name_key

    _rank = {
        MidweekAttendanceStatus.PRESENT: 3,
        MidweekAttendanceStatus.ONLINE: 2,
        MidweekAttendanceStatus.ABSENT: 1,
    }
    best: dict[str, ParsedMidweekAttendanceRow] = {}
    dropped = 0
    for r in parsed:
        k = member_name_key(r.display_name)
        if k not in best:
            best[k] = r
            continue
        if _rank.get(r.status, 0) > _rank.get(best[k].status, 0):
            dropped += 1
            best[k] = r
        else:
            dropped += 1
    return list(best.values()), dropped


__all__ = [
    "ParsedMidweekAttendanceRow",
    "midweek_status_from_venue_cell",
    "parse_midweek_attendance_sheet",
    "parse_midweek_service_date",
    "parse_date_from_sheet_name",
    "dedupe_midweek_by_member",
]
