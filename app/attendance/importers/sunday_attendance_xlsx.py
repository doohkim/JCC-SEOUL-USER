"""
주일예배 참석자 명단 시트 파싱 (예: ``2026.03.22 주일예배 참석자 명단``).

열 구조(행마다 동일):
  팀당 3열 — 이름 | 현장(부·온·지) | 인천 표시(V/v 등)

현장 열 값:
  - ``1``~``4`` : 해당 부. **인천 열에 체크(V/v/✓ 등)** 이면 인천 해당 부, 체크 없으면 서울 해당 부.
  - ``5`` : **3부·4부 연속 참석 표시**.
    - UI에서는 연참을 없애고,
    - 임포트 시에는 같은 출석행을 **3부(session_part=3)** 와 **4부(session_part=4)** 두 행으로 저장합니다.
  - ``온``/``지`` : 온라인·지교회

이름만 있고 현장·온·지가 비어 있으면 **행을 만들지 않음** (= 그날 주일 출석 데이터상 불참).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from attendance.choices import WorshipVenue


DATE_IN_TITLE_RE = re.compile(r"(\d{4})\.(\d{1,2})\.(\d{1,2})")


@dataclass(frozen=True)
class ParsedSundayAttendanceRow:
    """한 사람·한 팀 블록의 주일 출석 한 건."""

    display_name: str
    team_header: str
    venue: str
    session_part: int
    branch_label: str


def _strip_titles(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s*(팀장|셀장|부장|회장)\s*$", "", s).strip()
    return s


def _name_key(s: str) -> str:
    return re.sub(r"\s+", "", _strip_titles(s))


def parse_title_date(rows: list[tuple]) -> date | None:
    """상단 제목 셀에서 ``YYYY.MM.DD`` 추출."""
    for row in rows[:20]:
        if not row:
            continue
        for cell in row:
            if not isinstance(cell, str):
                continue
            m = DATE_IN_TITLE_RE.search(cell)
            if m:
                y, mo, d = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                return date(y, mo, d)
    return None


def _find_header_row_index(rows: list[tuple]) -> int | None:
    for i, row in enumerate(rows):
        if not row:
            continue
        if any(x == "부서 회장단" for x in row if x is not None):
            return i
    return None


def _find_subheader_row_index(rows: list[tuple], after: int) -> int | None:
    """``현장`` / ``인천`` 이 반복되는 행."""
    for i in range(after + 1, min(after + 8, len(rows))):
        row = rows[i]
        if not row:
            continue
        hits = sum(1 for x in row if x == "현장" or x == "인천")
        if hits >= 4:
            return i
    return None


def _team_starts_from_header_row(row: tuple) -> list[tuple[int, str]]:
    """
    팀 헤더 행에서 각 팀 블록 시작 열 인덱스(0-based).

    셀에 **「팀」** 또는 **「회장단」** 이 들어가면 팀 블록 시작으로 본다.
    """
    out: list[tuple[int, str]] = []
    if not row:
        return out
    for j, cell in enumerate(row):
        if isinstance(cell, str):
            raw_header = cell.strip()
            compact = raw_header.replace(" ", "")
            if raw_header and ("팀" in raw_header or "회장단" in raw_header):
                # 스냅샷: 부서 회장단은 공백을 제거한 형태로 표준화
                if compact == "부서회장단":
                    out.append((j, "부서회장단"))
                else:
                    # 기타 팀명은 엑셀 원문 그대로(공백 포함) 저장
                    out.append((j, raw_header))
    return out


def _parse_hyun_field(raw: Any) -> str | int | None:
    """현장 셀 → 부 번호(1~6), online, branch, None."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        n = int(raw)
        if 1 <= n <= 6:
            return n
        return None
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        if s in ("온", "온라인"):
            return "online"
        if s in ("지", "지교"):
            return "branch"
        if s.isdigit():
            n = int(s)
            if 1 <= n <= 6:
                return n
    return None


def _incheon_marked(raw: Any) -> bool:
    if raw is None or raw == "":
        return False
    if isinstance(raw, str):
        s = raw.strip().lower()
        return s in ("v", "✓", "√", "✔", "o", "○")
    if isinstance(raw, bool):
        return raw
    return False


def _to_venue_part_branch(
    hyun: str | int,
    incheon_cell: Any,
) -> tuple[str, int, str]:
    """(venue, session_part, branch_label)."""
    if hyun == "online":
        return WorshipVenue.ONLINE, 0, ""
    if hyun == "branch":
        return WorshipVenue.BRANCH, 0, ""
    if isinstance(hyun, int):
        part = hyun
        if _incheon_marked(incheon_cell):
            return WorshipVenue.INCHEON, part, ""
        return WorshipVenue.SEOUL, part, ""
    raise ValueError(f"unexpected hyun: {hyun!r}")


SECTION_LABELS = frozenset({"회장단", "간사단", "현장", "인천"})


def _row_display_name(cell: Any) -> str | None:
    if cell is None:
        return None
    if isinstance(cell, str):
        s = cell.strip()
        if not s or s in SECTION_LABELS:
            return None
        return s
    return None


def parse_sunday_attendance_sheet(
    rows: list[tuple],
) -> tuple[date | None, list[ParsedSundayAttendanceRow]]:
    """
    주일 참석자 명단 시트 전체 파싱.

    Returns:
        (service_date or None, parsed rows)
    """
    service_date = parse_title_date(rows)
    hi = _find_header_row_index(rows)
    if hi is None:
        raise ValueError("시트에서 '부서 회장단' 이 있는 헤더 행을 찾지 못했습니다.")
    team_starts = _team_starts_from_header_row(rows[hi])
    if not team_starts:
        raise ValueError("팀 열(부서 회장단·OO팀)을 찾지 못했습니다.")
    sub_i = _find_subheader_row_index(rows, hi)
    if sub_i is None:
        raise ValueError("'현장'/'인천' 서브헤더 행을 찾지 못했습니다.")

    data_begin = sub_i + 1
    out: list[ParsedSundayAttendanceRow] = []

    for i in range(data_begin, len(rows)):
        row = rows[i]
        if not row:
            continue
        first_txt = next((str(x).strip() for x in row if isinstance(x, str) and str(x).strip()), "")
        if first_txt and any(
            k in first_txt for k in ("합계", "참석자 명단 전체", "작성", "※", "주일예배")
        ):
            continue

        for start_col, team_header in team_starts:
            if start_col + 2 >= len(row):
                continue
            raw_name = _row_display_name(row[start_col])
            if not raw_name:
                continue
            hyun = _parse_hyun_field(row[start_col + 1])
            incheon_cell = row[start_col + 2]
            if hyun is None:
                continue
            venue, part, branch = _to_venue_part_branch(hyun, incheon_cell)
            if part == 5 and venue in (WorshipVenue.SEOUL, WorshipVenue.INCHEON):
                # legacy: 3·4부 연참(숫자 5)을 연참 없이 3부+4부로 분해
                out.append(
                    ParsedSundayAttendanceRow(
                        display_name=raw_name,
                        team_header=team_header,
                        venue=venue,
                        session_part=3,
                        branch_label=branch,
                    )
                )
                out.append(
                    ParsedSundayAttendanceRow(
                        display_name=raw_name,
                        team_header=team_header,
                        venue=venue,
                        session_part=4,
                        branch_label=branch,
                    )
                )
                continue

            out.append(
                ParsedSundayAttendanceRow(
                    display_name=raw_name,
                    team_header=team_header,
                    venue=venue,
                    session_part=part,
                    branch_label=branch,
                )
            )

    return service_date, out


__all__ = [
    "ParsedSundayAttendanceRow",
    "parse_sunday_attendance_sheet",
    "parse_title_date",
]
