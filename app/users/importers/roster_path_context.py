"""
엑셀 파일의 **루트 기준 상대 경로**에서 출석 명단 구분(연도·예배장소·부·지교회명) 추론.

권장 폴더 예시::

    rosters/
      2026/
        서울/1부/....xlsx
        서울/2부/....xlsx
        인천/....xlsx          → 부 미지정 시 DB에는 3부로 저장
        온라인/....xlsx
        지교회/강남/....xlsx

연도는 경로 또는 파일명에 ``20xx`` 가 포함되면 사용합니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from users.choices.attendance import WorshipVenue


def _norm_segment(seg: str) -> str:
    return seg.replace(" ", "").lower()


@dataclass(frozen=True)
class InferredRosterPath:
    year: int
    venue: str
    session_part: int
    branch_label: str


def infer_roster_path_context(rel_path: Path) -> InferredRosterPath | None:
    """
    :param rel_path: 임포트 루트에 대한 상대 경로 (파일명 포함).
    :return: 추론 불가 시 None (해당 파일 스킵).
    """
    parts = list(rel_path.parts)
    if len(parts) < 1:
        return None
    dirs = parts[:-1]
    filename = parts[-1]
    stem = Path(filename).stem

    year: int | None = None
    for chunk in list(dirs) + [stem]:
        m = re.search(r"(20\d{2})", chunk)
        if m:
            year = int(m.group(1))
            break
    if year is None:
        return None

    norm_dirs = [_norm_segment(p) for p in dirs]
    joined = "/".join(norm_dirs)

    venue: str | None = None
    if "온라인" in joined or "online" in joined:
        venue = WorshipVenue.ONLINE
    elif any(ns in ("지교회", "branch", "지교") for ns in norm_dirs):
        venue = WorshipVenue.BRANCH
    elif "서울" in joined or "seoul" in joined:
        venue = WorshipVenue.SEOUL
    elif "인천" in joined or "incheon" in joined:
        venue = WorshipVenue.INCHEON

    if venue is None:
        return None

    session_part: int | None = None
    for p in dirs:
        pn = _norm_segment(p)
        m = re.fullmatch(r"([1-4])부", pn)
        if m:
            session_part = int(m.group(1))
            break
        m = re.fullmatch(r"([1-4])bu", pn)
        if m:
            session_part = int(m.group(1))
            break
        m = re.search(r"(\d)부", pn)
        if m and m.group(1) in "1234":
            session_part = int(m.group(1))
            break

    branch_label = ""
    if venue == WorshipVenue.BRANCH:
        for i, p in enumerate(dirs):
            if _norm_segment(p) in ("지교회", "branch", "지교"):
                if i + 1 < len(dirs):
                    cand = dirs[i + 1]
                    cn = _norm_segment(cand)
                    if re.fullmatch(r"20\d{2}", cn):
                        continue
                    if re.fullmatch(r"[1-4]부", cn) or re.fullmatch(r"[1-4]bu", cn):
                        continue
                    branch_label = cand.strip()
                break

    if venue == WorshipVenue.INCHEON:
        if session_part is None:
            session_part = 3
    elif venue == WorshipVenue.SEOUL:
        if session_part is None:
            return None
    else:
        # 온라인 / 지교회
        session_part = 0

    return InferredRosterPath(
        year=year,
        venue=venue,
        session_part=session_part,
        branch_label=branch_label,
    )
