"""수련회 대시보드·결과 집계."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.db.models import Count
from django.db.models.functions import TruncHour
from django.utils import timezone

from retreat.models import (
    RetreatAttendance,
    RetreatAttendee,
    RetreatEvent,
    RetreatGroup,
    RetreatSession,
    RetreatSessionAttendee,
)
from retreat.services.check_in_stamps import backfill_missing_check_in_stamps
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


def build_realtime_dashboard(
    event: RetreatEvent,
    user,
    *,
    staff_view: bool,
) -> dict[str, Any]:
    """현재 입·퇴실 상태(RetreatAttendee) 기반 실시간 대시보드.

    - 조별 참석 인원(한번이라도 입실 = 입실+퇴실)
    - 지역·부서별 입실전/입실/퇴실/참석 인원
    - 1시간 단위 입실·퇴실 추이
    """
    restrict = not staff_view
    groups = list(_group_queryset(event, user, restrict_to_user_groups=restrict))
    group_ids = [g.id for g in groups]

    status_rows = (
        RetreatAttendee.objects.filter(group_id__in=group_ids)
        .values("group_id", "check_in_status")
        .annotate(c=Count("id"))
    )
    status_by_group: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in status_rows:
        status_by_group[row["group_id"]][row["check_in_status"]] = row["c"]

    S = RetreatAttendee.CheckInStatus
    by_group = []
    for g in groups:
        c = status_by_group.get(g.id, {})
        pending = c.get(S.PENDING, 0)
        checked_in = c.get(S.CHECKED_IN, 0)
        checked_out = c.get(S.CHECKED_OUT, 0)
        attended = checked_in + checked_out
        by_group.append(
            {
                "group_id": g.id,
                "name": g.name,
                "region": g.region.name,
                "region_id": g.region_id,
                "division": g.division.name,
                "division_id": g.division_id,
                "pending": pending,
                "checked_in": checked_in,
                "checked_out": checked_out,
                "attended": attended,
                "total": pending + checked_in + checked_out,
            }
        )

    by_division = _rollup_realtime_by_region_division(by_group)
    # 레거시 데이터: 입실 상태인데 checked_in_at 이 비어 있으면 추이 집계에서 누락됨
    backfill_missing_check_in_stamps(group_ids)
    hourly = _hourly_check_in_out(group_ids)

    grand_pending = sum(r["pending"] for r in by_group)
    grand_in = sum(r["checked_in"] for r in by_group)
    grand_out = sum(r["checked_out"] for r in by_group)
    grand_attended = grand_in + grand_out

    return {
        "generated_at": timezone.localtime().isoformat(),
        "by_group": by_group,
        "by_division": by_division,
        "hourly": hourly,
        "grand_total": {
            "pending": grand_pending,
            "checked_in": grand_in,
            "checked_out": grand_out,
            "attended": grand_attended,
            "total": grand_pending + grand_in + grand_out,
        },
    }


def _rollup_realtime_by_region_division(by_group: list[dict]) -> list[dict]:
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
                "pending": 0,
                "checked_in": 0,
                "checked_out": 0,
                "attended": 0,
                "total": 0,
            }
        item = rd_map[key]
        item["group_names"].append(row["name"])
        item["pending"] += row["pending"]
        item["checked_in"] += row["checked_in"]
        item["checked_out"] += row["checked_out"]
        item["attended"] += row["attended"]
        item["total"] += row["total"]

    result = []
    for item in rd_map.values():
        names = item.pop("group_names")
        item["group_range"] = _format_group_range(names)
        result.append(item)
    return sorted(result, key=lambda x: (x["region"], x["division"]))


def _hourly_check_in_out(group_ids: list[int]) -> list[dict]:
    """1시간 단위 입실·퇴실 건수 추이 (활동이 있는 시간대만)."""
    buckets: dict[Any, dict[str, int]] = defaultdict(
        lambda: {"checked_in": 0, "checked_out": 0}
    )

    in_rows = (
        RetreatAttendee.objects.filter(
            group_id__in=group_ids,
            checked_in_at__isnull=False,
            check_in_status__in=(
                RetreatAttendee.CheckInStatus.CHECKED_IN,
                RetreatAttendee.CheckInStatus.CHECKED_OUT,
            ),
        )
        .annotate(h=TruncHour("checked_in_at"))
        .values("h")
        .annotate(c=Count("id"))
    )
    for row in in_rows:
        buckets[row["h"]]["checked_in"] = row["c"]

    out_rows = (
        RetreatAttendee.objects.filter(
            group_id__in=group_ids,
            checked_out_at__isnull=False,
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
        )
        .annotate(h=TruncHour("checked_out_at"))
        .values("h")
        .annotate(c=Count("id"))
    )
    for row in out_rows:
        buckets[row["h"]]["checked_out"] = row["c"]

    result = []
    for hour in sorted(buckets.keys()):
        local = timezone.localtime(hour)
        result.append(
            {
                "hour": local.isoformat(),
                "label": local.strftime("%m/%d %H:00"),
                "checked_in": buckets[hour]["checked_in"],
                "checked_out": buckets[hour]["checked_out"],
            }
        )
    return result


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


def build_results_analytics(
    event: RetreatEvent,
    user,
    *,
    staff_view: bool,
) -> dict[str, Any]:
    """결과 시각화용 세션×조 매트릭스.

    - groups: 조 메타(이름·지역·부서)
    - sessions: 출석부별 조 present/registered 및 합계 (정렬: sequence→occurs_at→id)
    꺽은선(세션별 조별 추이)·도넛(조별 비중)·막대(조별 참석률) 렌더에 사용.
    """
    restrict = not staff_view
    groups = list(_group_queryset(event, user, restrict_to_user_groups=restrict))
    group_ids = [g.id for g in groups]
    group_meta = [
        {
            "group_id": g.id,
            "name": g.name,
            "region": g.region.name,
            "division": g.division.name,
        }
        for g in groups
    ]

    sessions = list(
        visible_retreat_sessions_for(user, event).order_by(
            "sequence", "occurs_at", "id"
        )
    )

    sessions_out: list[dict[str, Any]] = []
    for s in sessions:
        att = _attendance_counts_by_group(s.id)
        reg = _enrollment_totals_by_group(s.id)
        groups_data: dict[str, dict[str, int]] = {}
        total_present = 0
        total_registered = 0
        for gid in group_ids:
            present = att.get(gid, {}).get(RetreatAttendance.Status.PRESENT, 0)
            registered = reg.get(gid, 0)
            groups_data[str(gid)] = {"present": present, "registered": registered}
            total_present += present
            total_registered += registered
        sessions_out.append(
            {
                "id": s.id,
                "name": s.name,
                "occurs_at": s.occurs_at.isoformat() if s.occurs_at else None,
                "groups": groups_data,
                "total_present": total_present,
                "total_registered": total_registered,
            }
        )

    return {"groups": group_meta, "sessions": sessions_out}
