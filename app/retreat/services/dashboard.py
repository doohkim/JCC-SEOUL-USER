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
    RetreatPickup,
    RetreatSession,
    RetreatSessionAttendee,
)
from retreat.services.lodging_roster import lodging_eligible_filter
from retreat.services.participation import (
    absent_attendee_keys,
    participating_filter,
    pickup_visible_for_participation,
)
from users.permissions import (
    visible_retreat_groups_for,
    visible_retreat_sessions_for,
)


def _group_queryset(event: RetreatEvent, user, *, restrict_to_user_groups: bool):
    qs = (
        visible_retreat_groups_for(user, event)
        .select_related("region", "division")
        .order_by("order", "id")
    )
    if restrict_to_user_groups and not _is_event_wide_for_user(user, event):
        leader_group_ids = set(
            user.retreat_group_memberships.filter(group__event=event).values_list(
                "group_id", flat=True
            )
        )
        if leader_group_ids:
            qs = qs.filter(id__in=leader_group_ids)
    return qs


def _is_event_wide_for_user(user, event: RetreatEvent) -> bool:
    """집회 전체 조 집계·보기 — 슈퍼유저·해당 집회 회장단."""
    if user.is_superuser:
        return True
    from users.permissions import is_retreat_council

    return is_retreat_council(user, event)


def _event_group_ids(event: RetreatEvent) -> list[int]:
    return list(
        RetreatGroup.objects.filter(event=event).values_list("id", flat=True)
    )


def _leader_group_ids_for_event(user, event: RetreatEvent) -> list[int]:
    """집회에서 조장/부조장으로 소속된 조 id 목록."""
    if not user or not getattr(user, "is_authenticated", False):
        return []
    return list(
        user.retreat_group_memberships.filter(group__event=event).values_list(
            "group_id", flat=True
        )
    )


def _summary_scope_group_ids(
    event: RetreatEvent, user, *, staff_view: bool
) -> list[int]:
    """요약 카드(미배정·차량 지원) 집계 범위.

    - staff_view(회장단·슈퍼유저): 집회 전체 조
    - 조장/부조장: 본인 조만
    - 목사/전도사 등: ``visible_retreat_groups_for`` (담당 지역·부서 조)
    """
    if staff_view:
        return _event_group_ids(event)
    leader_ids = _leader_group_ids_for_event(user, event)
    if leader_ids:
        return leader_ids
    return list(visible_retreat_groups_for(user, event).values_list("id", flat=True))


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
    first, last = names[0], names[-1]
    # "5조~22조" 대신 "5~22조": 시작·끝이 같은 접미사("조")면 시작쪽 접미사는 생략
    if first.endswith("조") and last.endswith("조"):
        first = first[:-1]
    return f"{first}~{last}"


def _effective_check_in_status(check_in_at, check_out_at, now) -> str:
    """입실/퇴실 시각과 현재 시각으로 실시간 입·퇴실 상태를 계산한다.

    - 입실 시각이 없거나 아직 오지 않았으면 → 입실전(pending)
    - 퇴실 시각이 지났으면 → 퇴실(checked_out)
    - 그 외(입실 시각 <= now) → 입실(checked_in)

    저장된 check_in_status 가 아니라 시각 필드만으로 판정하므로, 주기 작업 없이도
    조회 시점 기준으로 항상 실시간 현황을 반영한다.
    """
    S = RetreatAttendee.CheckInStatus
    if check_in_at is None or check_in_at > now:
        return S.PENDING
    if check_out_at is not None and check_out_at <= now:
        return S.CHECKED_OUT
    return S.CHECKED_IN


def build_realtime_dashboard(
    event: RetreatEvent,
    user,
    *,
    staff_view: bool,
    now=None,
) -> dict[str, Any]:
    """입실/퇴실 시각 기반 실시간 대시보드.

    저장된 입·퇴실 상태가 아니라 조원의 입실/퇴실 시각(`expected_check_in_at`/
    `expected_check_out_at`)과 현재 시각을 비교해 상태를 실시간으로 계산한다.

    - 조별 참석 인원(현재 입실 상태 = 입실 시각 경과 & 퇴실 전)
    - 지역·부서별 입실전/입실/퇴실/참석(입실+퇴실) 인원
    - 1시간 단위 입실·퇴실 추이(입실/퇴실 시각 기준, 현재 시각까지 경과분만)
    """
    now = now or timezone.now()
    restrict = not staff_view
    groups = list(_group_queryset(event, user, restrict_to_user_groups=restrict))
    group_ids = [g.id for g in groups]

    time_rows = participating_filter(
        RetreatAttendee.objects.filter(group_id__in=group_ids)
    ).values_list("group_id", "expected_check_in_at", "expected_check_out_at")
    status_by_group: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for gid, check_in_at, check_out_at in time_rows:
        eff = _effective_check_in_status(check_in_at, check_out_at, now)
        status_by_group[gid][eff] += 1

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
    hourly = _hourly_check_in_out(group_ids, now)

    grand_pending = sum(r["pending"] for r in by_group)
    grand_in = sum(r["checked_in"] for r in by_group)
    grand_out = sum(r["checked_out"] for r in by_group)
    grand_attended = grand_in + grand_out
    grand_all = grand_pending + grand_in + grand_out
    grand_absent = RetreatAttendee.objects.filter(
        group_id__in=group_ids,
        participation_status=RetreatAttendee.ParticipationStatus.ABSENT,
    ).count()

    summary = _build_dashboard_summary(
        event,
        user=user,
        staff_view=staff_view,
        now=now,
        checked_in=grand_in,
        attended=grand_attended,
        total=grand_all,
    )

    return {
        "generated_at": timezone.localtime(now).isoformat(),
        "by_group": by_group,
        "by_division": by_division,
        "hourly": hourly,
        "grand_total": {
            "pending": grand_pending,
            "checked_in": grand_in,
            "checked_out": grand_out,
            "attended": grand_attended,
            "total": grand_all,
            "absent": grand_absent,
        },
        "summary": summary,
    }


def _build_dashboard_summary(
    event: RetreatEvent,
    user,
    *,
    staff_view: bool,
    now,
    checked_in: int,
    attended: int,
    total: int,
) -> dict[str, Any]:
    """상단 요약 카드용 집계.

    - 실시간 참석: 입실 인원 / 총 참석인원, 전체 인원 대비 입실 비율(%)
    - 미배정: 숙박 대상(참석·입실 예정·퇴실 제외) 중 호실 미배정 조원 수
      - 조장/부조장: 본인 조 조원만
      - 회장단·슈퍼유저(staff_view): 집회 전체 조
      - 목사/전도사: 담당 지역·부서 조
    - 차량 지원: 당일(현재 시각 기준) 열차 시각이 잡힌 픽업 인원 수
      - 조장/부조장: 본인 조 신청만
      - 회장단·슈퍼유저(staff_view): 집회 전체 조
      - 목사/전도사: 담당 지역·부서 조
    """
    attend_percent = round(checked_in / total * 100) if total else 0

    scope_group_ids = _summary_scope_group_ids(event, user, staff_view=staff_view)

    lodging_unassigned = lodging_eligible_filter(
        RetreatAttendee.objects.filter(
            group_id__in=scope_group_ids, lodging_room__isnull=True
        )
    ).count()

    today = timezone.localdate(now)
    pickups = RetreatPickup.objects.filter(event=event, train_time__date=today)
    if not staff_view:
        pickups = pickups.filter(group_id__in=scope_group_ids)
    absent_keys = absent_attendee_keys(
        _event_group_ids(event) if staff_view else scope_group_ids
    )
    car_today = sum(
        1
        for p in pickups
        if pickup_visible_for_participation(p, absent_keys=absent_keys)
    )

    return {
        "checked_in": checked_in,
        "attended": attended,
        "total": total,
        "attend_percent": attend_percent,
        "lodging_unassigned": lodging_unassigned,
        "car_today": car_today,
    }


def build_group_attendance_board(
    event: RetreatEvent,
    user,
    *,
    staff_view: bool,
    now=None,
) -> dict[str, Any]:
    """조별 조원 명단 + 실시간 입·퇴실 상태 보드.

    전체 조를 열(column)로, 각 조의 조원을 행으로 나열해 한눈에 참석 현황을
    파악하도록 한다. 상태는 ``build_realtime_dashboard`` 와 동일하게 입실/퇴실
    시각과 현재 시각을 비교해 실시간으로 계산한다.
    """
    now = now or timezone.now()
    # 회장단·슈퍼유저(staff_view)는 전체 조를, 그 외는 visible_retreat_groups_for 범위.
    if staff_view:
        groups_qs = (
            RetreatGroup.objects.filter(event=event)
            .select_related("region", "division")
            .order_by("order", "id")
        )
    else:
        groups_qs = (
            visible_retreat_groups_for(user, event)
            .select_related("region", "division")
            .order_by("order", "id")
        )
    groups = list(groups_qs)
    group_ids = [g.id for g in groups]

    S = RetreatAttendee.CheckInStatus
    status_labels = dict(S.choices)
    role_labels = dict(RetreatAttendee.MemberRole.choices)
    status_order = {S.CHECKED_IN: 0, S.CHECKED_OUT: 1, S.PENDING: 2}

    members_by_group: dict[int, list[dict]] = defaultdict(list)
    attendee_rows = participating_filter(
        RetreatAttendee.objects.filter(group_id__in=group_ids)
    ).values(
        "group_id",
        "name",
        "member_role",
        "gender",
        "expected_check_in_at",
        "expected_check_out_at",
    ).order_by("name", "id")
    for row in attendee_rows:
        eff = _effective_check_in_status(
            row["expected_check_in_at"], row["expected_check_out_at"], now
        )
        members_by_group[row["group_id"]].append(
            {
                "name": row["name"],
                "status": eff,
                "status_label": status_labels.get(eff, eff),
                "member_role": row["member_role"],
                "member_role_label": role_labels.get(
                    row["member_role"], row["member_role"]
                ),
                "gender": row["gender"],
            }
        )

    groups_out: list[dict] = []
    grand = {
        "pending": 0,
        "checked_in": 0,
        "checked_out": 0,
        "attended": 0,
        "total": 0,
    }
    for g in groups:
        members = members_by_group.get(g.id, [])
        members.sort(key=lambda m: (status_order.get(m["status"], 9), m["name"]))
        pending = sum(1 for m in members if m["status"] == S.PENDING)
        checked_in = sum(1 for m in members if m["status"] == S.CHECKED_IN)
        checked_out = sum(1 for m in members if m["status"] == S.CHECKED_OUT)
        attended = checked_in + checked_out
        groups_out.append(
            {
                "group_id": g.id,
                "name": g.name,
                "region": g.region.name,
                "division": g.division.name,
                "pending": pending,
                "checked_in": checked_in,
                "checked_out": checked_out,
                "attended": attended,
                "total": len(members),
                "members": members,
            }
        )
        grand["pending"] += pending
        grand["checked_in"] += checked_in
        grand["checked_out"] += checked_out
        grand["attended"] += attended
        grand["total"] += len(members)

    return {
        "generated_at": timezone.localtime(now).isoformat(),
        "groups": groups_out,
        "grand_total": grand,
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


def _hourly_check_in_out(group_ids: list[int], now) -> list[dict]:
    """1시간 단위 입실·퇴실 건수 추이.

    입실/퇴실 시각 필드 기준으로, 현재 시각까지 경과한 건만 집계한다(미래 예정 제외).
    """
    buckets: dict[Any, dict[str, int]] = defaultdict(
        lambda: {"checked_in": 0, "checked_out": 0}
    )

    in_rows = (
        participating_filter(
            RetreatAttendee.objects.filter(
                group_id__in=group_ids,
                expected_check_in_at__isnull=False,
                expected_check_in_at__lte=now,
            )
        )
        .annotate(h=TruncHour("expected_check_in_at"))
        .values("h")
        .annotate(c=Count("id"))
    )
    for row in in_rows:
        buckets[row["h"]]["checked_in"] = row["c"]

    out_rows = (
        participating_filter(
            RetreatAttendee.objects.filter(
                group_id__in=group_ids,
                expected_check_out_at__isnull=False,
                expected_check_out_at__lte=now,
            )
        )
        .annotate(h=TruncHour("expected_check_out_at"))
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
