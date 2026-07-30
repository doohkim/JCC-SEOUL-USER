"""수련회 대시보드·결과 집계."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any

from django.db.models import Count
from django.utils import timezone

from retreat.models import (
    RetreatAttendance,
    RetreatAttendee,
    RetreatEvent,
    RetreatGroup,
    RetreatPickup,
    RetreatSession,
    RetreatSessionAttendee,
    RetreatTravelPreset,
)
from retreat.services.effective_check_in import status_from_expected_times
from retreat.services.lodging_roster import lodging_eligible_filter
from retreat.services.participation import (
    absent_attendee_keys,
    participating_filter,
    pickup_visible_for_participation,
)
from retreat.services.account_retired import visible_attendees_for, visible_pickups_for
from retreat.services.travel_presets import (
    travel_bucket_key,
    travel_column_defs,
    travel_fixed_and_occurs_map,
)
from users.permissions import (
    get_retreat_capabilities,
    visible_retreat_groups_for,
    visible_retreat_sessions_for,
)


def _group_queryset(event: RetreatEvent, user, *, restrict_to_user_groups: bool):
    qs = (
        visible_retreat_groups_for(user, event)
        .select_related("region", "division")
        .prefetch_related("extra_scopes__region", "extra_scopes__division")
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
    """집회 전체 조 집계·보기 — 슈퍼유저·집회 전체 범위 운영진."""
    from users.permissions import can_view_retreat_all

    return can_view_retreat_all(user, event)


def _event_group_ids(event: RetreatEvent) -> list[int]:
    return list(RetreatGroup.objects.filter(event=event).values_list("id", flat=True))


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
    group_by_id = {g.id: g for g in groups}
    caps = get_retreat_capabilities(user, event)
    scope_kind = "event" if staff_view else caps.scope.kind
    scope_region_id = None if staff_view else caps.scope.region_id
    scope_division_id = None if staff_view else caps.scope.division_id
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
                "scope_labels": _scope_labels_for_group(g),
                "present": present,
                "absent": counts.get(RetreatAttendance.Status.ABSENT, 0),
                "total_attendees": total_by_group.get(g.id, 0),
                "entered": present,
            }
        )

    by_division = _build_division_rows_without_scope_duplication(
        by_group,
        group_by_id,
        scope_kind=scope_kind,
        scope_region_id=scope_region_id,
        scope_division_id=scope_division_id,
        count_keys=("present",),
        rollup_fn=_rollup_by_region_division,
        multi_row_extra={
            "entered": "__present__",
            "left_scheduled": 0,
            "current": "__present__",
            "final_attendance": "__present__",
        },
    )
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


def _format_combined_scope_label(scopes: list[dict[str, Any]]) -> str:
    """다스코프 조 지역·부서 표시.

    - 부서 동일: 대구·대전·세종 · 청년부
    - 지역 동일: 인천 · 청년부·대학부
    - 그 외: 콤마로 나열
    """
    if not scopes:
        return "-"
    if len(scopes) == 1:
        return f"{scopes[0]['region']} · {scopes[0]['division']}"
    regions = [str(s.get("region") or "").strip() for s in scopes]
    divisions = [str(s.get("division") or "").strip() for s in scopes]
    region_set = {r for r in regions if r}
    division_set = {d for d in divisions if d}
    if len(division_set) == 1:
        return f"{'·'.join(regions)} · {next(iter(division_set))}"
    if len(region_set) == 1:
        return f"{next(iter(region_set))} · {'·'.join(divisions)}"
    return ", ".join(
        f"{s.get('region', '')} · {s.get('division', '')}".strip(" ·") for s in scopes
    )


def _scope_fingerprint(scopes: list[dict[str, Any]]) -> tuple:
    return tuple(
        sorted(
            (int(s["region_id"]), int(s["division_id"]))
            for s in scopes
            if s.get("region_id") is not None and s.get("division_id") is not None
        )
    )


def _build_division_rows_without_scope_duplication(
    by_group: list[dict[str, Any]],
    group_by_id: dict[int, RetreatGroup],
    *,
    scope_kind: str,
    scope_region_id: int | None,
    scope_division_id: int | None,
    count_keys: tuple[str, ...],
    rollup_fn,
    multi_row_extra: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """지역·부서 표용 행 생성.

    - 단일 스코프 조: 기존처럼 (지역, 부서)로 묶어 조 범위를 합침
    - 다스코프 조: 인원 복제 없이, 동일 스코프 조합끼리 한 행으로 합침
      (예: 인천 청년부+대학부 9~16조 → 1행)
    """
    single_scope_rows: list[dict[str, Any]] = []
    multi_buckets: dict[tuple, dict[str, Any]] = {}
    for row in by_group:
        group = group_by_id[row["group_id"]]
        scopes = _visible_rollup_scope_rows_for_group(
            group,
            scope_kind=scope_kind,
            scope_region_id=scope_region_id,
            scope_division_id=scope_division_id,
        )
        if not scopes:
            continue
        if len(scopes) == 1:
            scope_row = scopes[0]
            single_scope_rows.append(
                {
                    **row,
                    "region": scope_row["region"],
                    "region_id": scope_row["region_id"],
                    "division": scope_row["division"],
                    "division_id": scope_row["division_id"],
                }
            )
            continue

        counts = {key: int(row.get(key, 0) or 0) for key in count_keys}
        if multi_row_extra:
            present = int(row.get("present", 0) or 0)
            counts = {
                **counts,
                **{
                    k: (present if v == "__present__" else int(v or 0))
                    for k, v in multi_row_extra.items()
                },
            }

        fp = _scope_fingerprint(scopes)
        bucket = multi_buckets.get(fp)
        if bucket is None:
            multi_buckets[fp] = {
                "region": _format_combined_scope_label(scopes),
                "region_id": scopes[0]["region_id"],
                "division": "",
                "division_id": scopes[0]["division_id"],
                "filter_regions": list(
                    dict.fromkeys(scope["region"] for scope in scopes)
                ),
                "filter_divisions": list(
                    dict.fromkeys(scope["division"] for scope in scopes)
                ),
                "group_names": [row["name"]],
                **counts,
            }
        else:
            bucket["group_names"].append(row["name"])
            for key, value in counts.items():
                bucket[key] = int(bucket.get(key, 0) or 0) + value

    multi_scope_rows: list[dict[str, Any]] = []
    for bucket in multi_buckets.values():
        names = bucket.pop("group_names")
        multi_scope_rows.append(
            {
                **bucket,
                "group_range": _format_group_range(names),
            }
        )

    rolled = rollup_fn(single_scope_rows)
    return rolled + multi_scope_rows


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


def _scope_rows_for_group(group: RetreatGroup) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "region": group.region.name,
            "region_id": group.region_id,
            "division": group.division.name,
            "division_id": group.division_id,
        }
    ]
    seen = {(group.region_id, group.division_id)}
    for scope in group.extra_scopes.all():
        pair = (scope.region_id, scope.division_id)
        if pair in seen:
            continue
        seen.add(pair)
        rows.append(
            {
                "region": scope.region.name,
                "region_id": scope.region_id,
                "division": scope.division.name,
                "division_id": scope.division_id,
            }
        )
    return rows


def _visible_rollup_scope_rows_for_group(
    group: RetreatGroup,
    *,
    scope_kind: str,
    scope_region_id: int | None,
    scope_division_id: int | None,
) -> list[dict[str, Any]]:
    rows = _scope_rows_for_group(group)
    if scope_kind == "event":
        return rows
    if scope_kind == "region" and scope_region_id:
        filtered = [row for row in rows if row["region_id"] == scope_region_id]
        if filtered:
            return filtered
    if scope_kind == "division" and scope_division_id:
        filtered = [row for row in rows if row["division_id"] == scope_division_id]
        if filtered:
            return filtered
    return [rows[0]]


def _scope_labels_for_group(group: RetreatGroup) -> list[dict[str, Any]]:
    labels: list[dict[str, Any]] = []
    for idx, row in enumerate(_scope_rows_for_group(group)):
        labels.append(
            {
                "region": row["region"],
                "division": row["division"],
                "is_primary": idx == 0,
            }
        )
    return labels


def _effective_check_in_status(
    check_in_at,
    check_out_at,
    now,
    *,
    manually_set: bool = False,
    stored_status: str | None = None,
) -> str:
    """입실/퇴실 시각과 현재 시각으로 실시간 입·퇴실 상태를 계산한다.

    수동 예외 상태가 있으면 저장 상태를 우선한다.
    """
    if manually_set and stored_status:
        return stored_status
    return status_from_expected_times(check_in_at, check_out_at, now)


def _travel_count_for_col(col: dict[str, Any], counts: dict) -> int:
    if col["code"] in ("__custom__", "__unset__"):
        return int(counts.get(col["code"], 0))
    return int(counts.get(col["id"], 0))


def _travel_rows_from_counts(
    columns: list[dict[str, Any]], counts: dict
) -> list[dict[str, Any]]:
    return [
        {
            "id": col["id"],
            "code": col["code"],
            "label": col["label"],
            "manual": col["manual"],
            "count": _travel_count_for_col(col, counts),
        }
        for col in columns
    ]


def _travel_vector_from_counts(
    columns: list[dict[str, Any]], counts: dict
) -> list[int]:
    return [_travel_count_for_col(col, counts) for col in columns]


def build_travel_summary_for_attendee_times(
    event: RetreatEvent,
    time_rows: list[tuple],
    groups: list | None = None,
) -> dict[str, Any]:
    """조원 expected 입·퇴실 시각을 집회 프리셋 웨이브에 매칭한 집계.

    ``groups`` 가 있으면 조×웨이브 매트릭스(``by_group``)도 함께 반환한다.
    """
    presets = list(
        RetreatTravelPreset.objects.filter(event=event, is_active=True).order_by(
            "direction", "sort_order", "id"
        )
    )
    arrival_presets = [
        p for p in presets if p.direction == RetreatTravelPreset.Direction.ARRIVAL
    ]
    departure_presets = [
        p for p in presets if p.direction == RetreatTravelPreset.Direction.DEPARTURE
    ]
    arrival_fixed, arrival_occurs = travel_fixed_and_occurs_map(arrival_presets)
    departure_fixed, departure_occurs = travel_fixed_and_occurs_map(departure_presets)
    arrival_columns = travel_column_defs(arrival_fixed)
    departure_columns = travel_column_defs(departure_fixed)

    arrival_counts: dict[str | int, int] = defaultdict(int)
    departure_counts: dict[str | int, int] = defaultdict(int)
    arrival_by_gid: dict[int, dict[str | int, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    departure_by_gid: dict[int, dict[str | int, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for row in time_rows:
        if len(row) >= 5:
            gid, in_at, out_at, in_custom, out_custom = row[:5]
        else:
            gid, in_at, out_at = row[:3]
            in_custom = out_custom = None
        a_key = travel_bucket_key(in_at, arrival_occurs, is_custom=in_custom)
        d_key = travel_bucket_key(out_at, departure_occurs, is_custom=out_custom)
        arrival_counts[a_key] += 1
        departure_counts[d_key] += 1
        if gid is not None:
            arrival_by_gid[int(gid)][a_key] += 1
            departure_by_gid[int(gid)][d_key] += 1

    arrival = _travel_rows_from_counts(arrival_columns, arrival_counts)
    departure = _travel_rows_from_counts(departure_columns, departure_counts)

    by_group_rows: list[dict[str, Any]] = []
    for g in groups or []:
        a_vec = _travel_vector_from_counts(
            arrival_columns, arrival_by_gid.get(g.id, {})
        )
        d_vec = _travel_vector_from_counts(
            departure_columns, departure_by_gid.get(g.id, {})
        )
        by_group_rows.append(
            {
                "group_id": g.id,
                "name": g.name,
                "region": g.region.name,
                "division": g.division.name,
                "arrival": a_vec,
                "departure": d_vec,
                "arrival_total": sum(a_vec),
                "departure_total": sum(d_vec),
            }
        )

    return {
        "arrival": arrival,
        "departure": departure,
        "arrival_total": sum(r["count"] for r in arrival),
        "departure_total": sum(r["count"] for r in departure),
        "has_presets": bool(arrival_presets or departure_presets),
        "by_group": {
            "arrival_columns": arrival_columns,
            "departure_columns": departure_columns,
            "rows": by_group_rows,
        },
    }


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
    - 당일 1시간 단위 입·퇴실 전환수와 실시간·전체 참석 스냅샷
    """
    now = now or timezone.now()
    restrict = not staff_view
    groups = list(_group_queryset(event, user, restrict_to_user_groups=restrict))
    group_by_id = {g.id: g for g in groups}
    caps = get_retreat_capabilities(user, event)
    scope_kind = "event" if staff_view else caps.scope.kind
    scope_region_id = None if staff_view else caps.scope.region_id
    scope_division_id = None if staff_view else caps.scope.division_id
    group_ids = [g.id for g in groups]

    time_rows = list(
        participating_filter(
            visible_attendees_for(
                user, RetreatAttendee.objects.filter(group_id__in=group_ids)
            )
        ).values_list(
            "group_id",
            "expected_check_in_at",
            "expected_check_out_at",
            "arrival_travel_is_custom",
            "departure_travel_is_custom",
            "gender",
            "check_in_status_manually_set",
            "check_in_status",
        )
    )
    status_by_group: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    gender_by_group: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for (
        gid,
        check_in_at,
        check_out_at,
        _in_custom,
        _out_custom,
        gender,
        manually_set,
        stored_status,
    ) in time_rows:
        eff = _effective_check_in_status(
            check_in_at,
            check_out_at,
            now,
            manually_set=manually_set,
            stored_status=stored_status,
        )
        status_by_group[gid][eff] += 1
        if gender == RetreatAttendee.Gender.MALE:
            gender_by_group[gid]["male"] += 1
        elif gender == RetreatAttendee.Gender.FEMALE:
            gender_by_group[gid]["female"] += 1
        else:
            gender_by_group[gid]["gender_unknown"] += 1

    S = RetreatAttendee.CheckInStatus
    by_group = []
    for g in groups:
        c = status_by_group.get(g.id, {})
        gc = gender_by_group.get(g.id, {})
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
                "scope_labels": _scope_labels_for_group(g),
                "pending": pending,
                "checked_in": checked_in,
                "checked_out": checked_out,
                "attended": attended,
                "total": pending + checked_in + checked_out,
                "male": gc.get("male", 0),
                "female": gc.get("female", 0),
                "gender_unknown": gc.get("gender_unknown", 0),
            }
        )

    by_division = _build_division_rows_without_scope_duplication(
        by_group,
        group_by_id,
        scope_kind=scope_kind,
        scope_region_id=scope_region_id,
        scope_division_id=scope_division_id,
        count_keys=(
            "pending",
            "checked_in",
            "checked_out",
            "attended",
            "total",
            "male",
            "female",
            "gender_unknown",
        ),
        rollup_fn=_rollup_realtime_by_region_division,
    )
    hourly = _hourly_check_in_out(group_ids, now, user=user)

    grand_pending = sum(r["pending"] for r in by_group)
    grand_in = sum(r["checked_in"] for r in by_group)
    grand_out = sum(r["checked_out"] for r in by_group)
    grand_attended = grand_in + grand_out
    grand_all = grand_pending + grand_in + grand_out
    grand_male = sum(r["male"] for r in by_group)
    grand_female = sum(r["female"] for r in by_group)
    grand_gender_unknown = sum(r["gender_unknown"] for r in by_group)
    grand_absent = visible_attendees_for(
        user,
        RetreatAttendee.objects.filter(
            group_id__in=group_ids,
            participation_status=RetreatAttendee.ParticipationStatus.ABSENT,
        ),
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
    travel = build_travel_summary_for_attendee_times(event, time_rows, groups=groups)

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
            "male": grand_male,
            "female": grand_female,
            "gender_unknown": grand_gender_unknown,
        },
        "summary": summary,
        "travel": travel,
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
        visible_attendees_for(
            user,
            RetreatAttendee.objects.filter(
                group_id__in=scope_group_ids, lodging_room__isnull=True
            ),
        )
    ).count()

    today = timezone.localdate(now)
    pickups = visible_pickups_for(
        user, RetreatPickup.objects.filter(event=event, train_time__date=today)
    )
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
    travel_presets = list(
        RetreatTravelPreset.objects.filter(event=event, is_active=True).order_by(
            "direction", "sort_order", "id"
        )
    )
    arrival_fixed, arrival_occurs = travel_fixed_and_occurs_map(
        [
            preset
            for preset in travel_presets
            if preset.direction == RetreatTravelPreset.Direction.ARRIVAL
        ]
    )
    departure_fixed, departure_occurs = travel_fixed_and_occurs_map(
        [
            preset
            for preset in travel_presets
            if preset.direction == RetreatTravelPreset.Direction.DEPARTURE
        ]
    )
    arrival_columns = travel_column_defs(arrival_fixed)
    departure_columns = travel_column_defs(departure_fixed)

    def filter_options(columns):
        return [
            {
                "value": str(
                    column["code"]
                    if column["code"] in ("__custom__", "__unset__")
                    else column["id"]
                ),
                "label": column["label"],
                "color": column.get("color") or "",
                "manual": bool(column.get("manual")),
            }
            for column in columns
        ]

    members_by_group: dict[int, list[dict]] = defaultdict(list)
    attendee_rows = (
        visible_attendees_for(
            user, RetreatAttendee.objects.filter(group_id__in=group_ids)
        )
        .values(
            "group_id",
            "name",
            "participation_status",
            "member_role",
            "gender",
            "expected_check_in_at",
            "expected_check_out_at",
            "arrival_travel_is_custom",
            "departure_travel_is_custom",
            "check_in_status_manually_set",
            "check_in_status",
        )
        .order_by("name", "id")
    )
    for row in attendee_rows:
        is_absent = (
            row["participation_status"] == RetreatAttendee.ParticipationStatus.ABSENT
        )
        eff = (
            "absent"
            if is_absent
            else _effective_check_in_status(
                row["expected_check_in_at"],
                row["expected_check_out_at"],
                now,
                manually_set=row["check_in_status_manually_set"],
                stored_status=row["check_in_status"],
            )
        )
        members_by_group[row["group_id"]].append(
            {
                "name": row["name"],
                "status": eff,
                "status_label": "불참" if is_absent else status_labels.get(eff, eff),
                "participation_status": row["participation_status"],
                "participation_label": "불참" if is_absent else "참석",
                "member_role": row["member_role"],
                "member_role_label": role_labels.get(
                    row["member_role"], row["member_role"]
                ),
                "gender": row["gender"],
                "arrival_travel": str(
                    travel_bucket_key(
                        row["expected_check_in_at"],
                        arrival_occurs,
                        is_custom=row["arrival_travel_is_custom"],
                    )
                ),
                "departure_travel": str(
                    travel_bucket_key(
                        row["expected_check_out_at"],
                        departure_occurs,
                        is_custom=row["departure_travel_is_custom"],
                    )
                ),
            }
        )

    groups_out: list[dict] = []
    grand = {
        "roster_total": 0,
        "participating": 0,
        "absent": 0,
        "pending": 0,
        "checked_in": 0,
        "checked_out": 0,
        "attended": 0,
        "total": 0,
    }
    for g in groups:
        members = members_by_group.get(g.id, [])
        members.sort(key=lambda m: (status_order.get(m["status"], 9), m["name"]))
        participating = sum(1 for m in members if m["participation_status"] != "absent")
        absent = len(members) - participating
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
                "participating": participating,
                "absent": absent,
                "roster_total": len(members),
                "checked_in": checked_in,
                "checked_out": checked_out,
                "attended": attended,
                "total": participating,
                "members": members,
            }
        )
        grand["pending"] += pending
        grand["participating"] += participating
        grand["absent"] += absent
        grand["roster_total"] += len(members)
        grand["checked_in"] += checked_in
        grand["checked_out"] += checked_out
        grand["attended"] += attended
        grand["total"] += participating

    return {
        "generated_at": timezone.localtime(now).isoformat(),
        "groups": groups_out,
        "grand_total": grand,
        "travel_filters": {
            "arrival": filter_options(arrival_columns),
            "departure": filter_options(departure_columns),
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
                "male": 0,
                "female": 0,
                "gender_unknown": 0,
            }
        item = rd_map[key]
        item["group_names"].append(row["name"])
        item["pending"] += row["pending"]
        item["checked_in"] += row["checked_in"]
        item["checked_out"] += row["checked_out"]
        item["attended"] += row["attended"]
        item["total"] += row["total"]
        item["male"] += row.get("male", 0)
        item["female"] += row.get("female", 0)
        item["gender_unknown"] += row.get("gender_unknown", 0)

    result = []
    for item in rd_map.values():
        names = item.pop("group_names")
        item["group_range"] = _format_group_range(names)
        result.append(item)
    return sorted(result, key=lambda x: (x["region"], x["division"]))


def _hourly_check_in_out(group_ids: list[int], now, *, user) -> list[dict]:
    """당일 1시간 단위 입·퇴실 전환수와 상태 스냅샷.

    - 입실 전환수(``check_in_delta``): ``expected_check_in_at`` ∈ ``[H, H+1)``
    - 퇴실 전환수(``check_out_delta``): ``expected_check_out_at`` ∈ ``[H, H+1)``
    - 실시간 참석(``live``): 구간 종료 ``H+1`` 시점 ``checked_in`` 인원
    - 전체 참석(``attended``): 동일 시점 ``checked_in + checked_out``
    """
    local_now = timezone.localtime(now)
    day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)

    rows = list(
        participating_filter(
            visible_attendees_for(
                user,
                RetreatAttendee.objects.filter(group_id__in=group_ids),
            )
        ).values_list(
            "expected_check_in_at",
            "expected_check_out_at",
            "check_in_status_manually_set",
            "check_in_status",
        )
    )

    S = RetreatAttendee.CheckInStatus
    result: list[dict] = []
    for hour in range(24):
        hour_start = day_start + timedelta(hours=hour)
        hour_end = hour_start + timedelta(hours=1)
        label_end = "24:00" if hour == 23 else hour_end.strftime("%H:%M")
        label = f"{hour_start.strftime('%H:%M')} ~ {label_end}"

        check_in_delta = 0
        check_out_delta = 0
        live = 0
        checked_out = 0
        for check_in_at, check_out_at, manually_set, stored_status in rows:
            if check_in_at is not None:
                local_in = timezone.localtime(check_in_at)
                if hour_start <= local_in < hour_end:
                    check_in_delta += 1
            if check_out_at is not None:
                local_out = timezone.localtime(check_out_at)
                if hour_start <= local_out < hour_end:
                    check_out_delta += 1
            eff = _effective_check_in_status(
                check_in_at,
                check_out_at,
                hour_end,
                manually_set=manually_set,
                stored_status=stored_status,
            )
            if eff == S.CHECKED_IN:
                live += 1
            elif eff == S.CHECKED_OUT:
                checked_out += 1

        result.append(
            {
                "hour": hour_start.isoformat(),
                "label": label,
                "check_in_delta": check_in_delta,
                "check_out_delta": check_out_delta,
                "live": live,
                "attended": live + checked_out,
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
