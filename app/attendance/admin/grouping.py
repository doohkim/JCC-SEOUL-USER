"""Admin 인덱스 — ``attendance`` (출석)."""

from __future__ import annotations

ATTENDANCE_MODEL_GROUPS: dict[str, tuple[int, str, str]] = {
    "WorshipRosterScope": (10, "예배 명단 · 엑셀/스냅샷", "명단"),
    "WorshipRosterEntry": (10, "예배 명단 · 엑셀/스냅샷", "명단"),
    "AttendanceWeek": (20, "주간 출석부 · 주차·수토·주일", "주간출석"),
    "MidweekAttendanceRecord": (20, "주간 출석부 · 주차·수토·주일", "주간출석"),
    "SundayAttendanceLine": (20, "주간 출석부 · 주차·수토·주일", "주간출석"),
    "TeamAttendanceSession": (30, "팀 출석부 · 교시 칩", "팀출석"),
    "TeamMemberSlotAttendance": (30, "팀 출석부 · 교시 칩", "팀출석"),
}


def _annotate(models: list[dict], mapping: dict) -> list[dict]:
    out = []
    for m in models:
        m = dict(m)
        on = m.get("object_name") or ""
        order, section, tag = mapping.get(on, (999, "기타", "기타"))
        m["admin_group_order"] = order
        m["admin_group_section"] = section
        m["admin_group_tag"] = tag
        out.append(m)
    out.sort(key=lambda x: (x["admin_group_order"], x.get("name") or ""))
    return out


def group_attendance_models_for_template(models: list[dict]) -> list[dict]:
    annotated = _annotate(models, ATTENDANCE_MODEL_GROUPS)
    buckets: list[dict] = []
    key_to_idx: dict[tuple[int, str], int] = {}
    for m in annotated:
        k = (m["admin_group_order"], m["admin_group_section"])
        if k not in key_to_idx:
            key_to_idx[k] = len(buckets)
            buckets.append(
                {
                    "order": m["admin_group_order"],
                    "section": m["admin_group_section"],
                    "tag": m["admin_group_tag"],
                    "models": [],
                }
            )
        buckets[key_to_idx[k]]["models"].append(m)
    return buckets
