"""수련회 대시보드·결과 집계."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.db.models import Count

from retreat.models import (
    RetreatAttendance,
    RetreatEvent,
    RetreatGroup,
    RetreatSession,
    RetreatSessionAttendee,
)
from users.permissions import visible_retreat_groups_for, visible_retreat_sessions_for


def _group_queryset(event: RetreatEvent, user, *, restrict_to_user_groups: bool):
    qs = (
        visible_retreat_groups_for(user, event)
        .select_related("region", "division")
        .order_by("order", "id")
    )
    if restrict_to_user_groups and not (
        user.is_superuser or _is_staff_for_event(user, event)
    ):
        leader_group_ids = set(
            user.retreat_group_memberships.filter(group__event=event).values_list(
                "group_id", flat=True
            )
        )
        if leader_group_ids:
            qs = qs.filter(id__in=leader_group_ids)
    return qs


def _is_staff_for_event(user, event: RetreatEvent) -> bool:
    from users.permissions import is_retreat_staff

    return bool(user.is_superuser or is_retreat_staff(user, event))


def _attendance_counts_by_group(session_id: int) -> dict[int, dict[str, int]]:
    """group_id -> {status: count}."""
    rows = (
        RetreatAttendance.objects.filter(enrollment__session_id=session_id)
        .values("enrollment__source_group_id", "status")
        .annotate(c=Count("id"))
    )
    out: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        gid = row["enrollment__source_group_id"]
        if gid is None:
            continue
        out[gid][row["status"]] = row["c"]
    return {k: dict(v) for k, v in out.items()}


def _enrollment_totals_by_group(session_id: int) -> dict[int, int]:
    rows = (
        RetreatSessionAttendee.objects.filter(session_id=session_id)
        .values("source_group_id")
        .annotate(c=Count("id"))
    )
    return {
        row["source_group_id"]: row["c"]
        for row in rows
        if row["source_group_id"] is not None
    }


def build_session_dashboard(
    event: RetreatEvent,
    session: RetreatSession,
    user,
    *,
    staff_view: bool,
) -> dict[str, Any]:
    restrict = not staff_view
    groups = list(_group_queryset(event, user, restrict_to_user_groups=restrict))
    att_by_group = _attendance_counts_by_group(session.id)
    total_by_group = _enrollment_totals_by_group(session.id)

    by_group = []
    for g in groups:
        counts = att_by_group.get(g.id, {})
        present = counts.get(RetreatAttendance.Status.PRESENT, 0)
        by_group.append(
            {
                "group_id": g.id,
                "name": g.name,
                "region": g.region.name,
                "region_id": g.region_id,
                "division": g.division.name,
                "division_id": g.division_id,
                "present": present,
                "absent": counts.get(RetreatAttendance.Status.ABSENT, 0),
                "total_attendees": total_by_group.get(g.id, 0),
                "entered": present,
            }
        )

    by_division = _rollup_by_region_division(by_group)
    grand_total = sum(row["present"] for row in by_group)

    return {
        "session": {
            "id": session.id,
            "name": session.name,
            "occurs_at": session.occurs_at.isoformat() if session.occurs_at else None,
        },
        "by_group": by_group,
        "by_division": by_division,
        "grand_total": {
            "entered": grand_total,
            "left_scheduled": 0,
            "current": grand_total,
            "final_attendance": grand_total,
        },
    }


def _rollup_by_region_division(by_group: list[dict]) -> list[dict]:
    """(지역, 부서) 단위 조 범위·입실 집계."""
    rd_map: dict[tuple[int, int], dict] = {}
    for row in by_group:
        key = (row["region_id"], row["division_id"])
        if key not in rd_map:
            rd_map[key] = {
                "region": row["region"],
                "region_id": row["region_id"],
                "division": row["division"],
                "division_id": row["division_id"],
                "group_names": [],
                "entered": 0,
                "left_scheduled": 0,
                "current": 0,
                "final_attendance": 0,
            }
        rd_map[key]["group_names"].append(row["name"])
        rd_map[key]["entered"] += row["present"]
        rd_map[key]["current"] += row["present"]
        rd_map[key]["final_attendance"] += row["present"]

    result = []
    for item in rd_map.values():
        names = item.pop("group_names")
        item["group_range"] = _format_group_range(names)
        result.append(item)
    return sorted(result, key=lambda x: (x["region"], x["division"]))


def _format_group_range(names: list[str]) -> str:
    if not names:
        return "-"
    if len(names) == 1:
        return names[0]
    return f"{names[0]}~{names[-1]}"


def build_event_results(
    event: RetreatEvent,
    user,
    *,
    session: RetreatSession | None = None,
    staff_view: bool,
) -> dict[str, Any]:
    if session is None:
        session = (
            visible_retreat_sessions_for(user, event)
            .order_by("-created_at", "-id")
            .first()
        )
    if session is None:
        return {"session": None, "by_group": [], "grand_total": 0}

    data = build_session_dashboard(event, session, user, staff_view=staff_view)
    by_group = [
        {
            "group_id": r["group_id"],
            "name": r["name"],
            "region": r["region"],
            "division": r["division"],
            "count": r["present"],
        }
        for r in data["by_group"]
    ]
    return {
        "session": data["session"],
        "by_group": by_group,
        "grand_total": data["grand_total"]["final_attendance"],
    }
