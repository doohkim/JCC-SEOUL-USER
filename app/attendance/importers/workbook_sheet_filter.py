"""통합 워크북에서 처리할 시트 판별."""

from __future__ import annotations

from typing import Literal

SKIP_CONTAINS = (
    "사본",
    "주일 88",
    "주일 인천",
    "집회",
    "전도명단",
    "예상명단",
)

SheetKind = Literal["sunday", "wednesday", "saturday"]


def workbook_sheet_kind(sheet_name: str) -> SheetKind | None:
    s = sheet_name.strip()
    if not s:
        return None
    for bad in SKIP_CONTAINS:
        if bad in s:
            return None
    c = s.replace(" ", "")
    if "주일예배" in c:
        return "sunday"
    if "수요예배" in c:
        return "wednesday"
    if "토요예배" in c:
        return "saturday"
    return None


__all__ = ["SKIP_CONTAINS", "SheetKind", "workbook_sheet_kind"]
