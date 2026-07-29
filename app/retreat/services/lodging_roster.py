"""숙소 탭 전체 명단 — 집계·조회."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
import re

from django.contrib.auth import get_user_model
from django.db.models import Case, Count, IntegerField, Q, QuerySet, Value, When
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from retreat.models import RetreatAttendee, RetreatEvent, RetreatTravelPreset
from retreat.services.check_in_stamps import (
    is_attendee_profile_locked,
)
from retreat.services.lodging_stay import (
    is_lodging_stay_eligible,
    lodging_stay_display,
    lodging_stay_eligible_filter,
)
from retreat.services.participation import is_participating
from retreat.services.account_retired import visible_attendees_for
from retreat.services.effective_check_in import (
    effective_status,
    effective_status_expression,
)
from retreat.services.lodging_stay import resolve_lodging_stay_status
from retreat.services.staff_capabilities import effective_capabilities
from retreat.services.travel_presets import (
    travel_bucket_key,
    travel_filter_chip_defs,
    travel_fixed_and_occurs_map,
    travel_presets_for_event,
)
from users.permissions import visible_retreat_groups_for

User = get_user_model()


@dataclass(frozen=True)
class LodgingRosterSummary:
    count_total: int
    count_participating: int
    count_absent: int
    count_pending: int
    count_checked_in: int
    count_checked_out: int
    count_lodging_eligible: int
    count_lodging_unassigned: int


LODGING_ROSTER_PAGE_SIZE = 20


def _csv_values(params, key: str) -> set[str]:
    return {value for value in str(params.get(key, "") or "").split(",") if value}


def _range_datetime(value: str):
    parsed = parse_datetime(str(value or ""))
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def filter_and_sort_lodging_roster(attendees: list[RetreatAttendee], params) -> list:
    """전체 명단 UI의 필터·검색·정렬을 서버에서 동일하게 적용한다."""
    statuses = _csv_values(params, "status")
    lodging_stays = _csv_values(params, "lodgingStay")
    if not lodging_stays:
        legacy_stay = _csv_values(params, "stay")
        legacy_assign = _csv_values(params, "assign")
        legacy_lodging = _csv_values(params, "lodging")
        if "eligible" in legacy_stay or "eligible" in legacy_lodging:
            lodging_stays.update({"active", "unassigned"})
        if legacy_stay.intersection(
            {"ineligible", "na"}
        ) or legacy_lodging.intersection({"ineligible", "na"}):
            lodging_stays.update({"ended", "no_stay", "absent"})
        if "assigned" in legacy_assign or "assigned" in legacy_lodging:
            lodging_stays.add("active")
        if "unassigned" in legacy_assign or "unassigned" in legacy_lodging:
            lodging_stays.add("unassigned")
    genders = _csv_values(params, "gender")
    nights = _csv_values(params, "nights")
    arrivals = _csv_values(params, "arrivalTravel")
    departures = _csv_values(params, "departureTravel")
    regions = _csv_values(params, "region")
    divisions = _csv_values(params, "division")
    memo_only = "1" in _csv_values(params, "memo")
    query = str(params.get("q", "") or "").strip().lower()
    query_digits = re.sub(r"\D", "", query)
    date_from = _range_datetime(params.get("dateFrom", ""))
    date_to = _range_datetime(params.get("dateTo", ""))

    def matches(attendee):
        gender = attendee.gender or "__unset__"
        if statuses and attendee.check_in_status not in statuses:
            return False
        if lodging_stays and attendee.lodging_stay_status not in lodging_stays:
            return False
        if genders and gender not in genders:
            return False
        if nights:
            night_key = str(attendee.lodging_nights)
            if night_key not in nights and not (
                "2" in nights and attendee.lodging_nights >= 2
            ):
                return False
        if arrivals and str(attendee.arrival_travel_key) not in arrivals:
            return False
        if departures and str(attendee.departure_travel_key) not in departures:
            return False
        if regions and not regions.intersection(attendee.group_region_names):
            return False
        if divisions and not divisions.intersection(attendee.group_division_names):
            return False
        if date_from or date_to:
            starts_at = attendee.expected_check_in_at
            ends_at = attendee.expected_check_out_at
            if starts_at is None or ends_at is None:
                return False
            if date_to and starts_at > date_to:
                return False
            if date_from and ends_at < date_from:
                return False
        if memo_only and not (attendee.memo or "").strip():
            return False
        if query:
            name_match = query in (attendee.name or "").lower()
            phone_match = bool(
                query_digits and query_digits in re.sub(r"\D", "", attendee.phone or "")
            )
            if not name_match and not phone_match:
                return False
        return True

    filtered = [attendee for attendee in attendees if matches(attendee)]
    sort_key = str(params.get("sort", "") or "")
    reverse = str(params.get("dir", "asc") or "") == "desc"
    role_order = {"leader": 0, "vice_leader": 1, "teacher": 2, "member": 3}
    status_order = {"pending": 0, "checked_in": 1, "checked_out": 2}

    key_functions = {
        "group": lambda a: (a.group.name or "", a.name or ""),
        "name": lambda a: (a.name or "", a.id),
        "role": lambda a: (role_order.get(a.member_role, 99), a.name or ""),
        "status": lambda a: (status_order.get(a.check_in_status, 99), a.name or ""),
        "expectedIn": lambda a: (
            a.expected_check_in_at is None,
            a.expected_check_in_at or timezone.now(),
            a.name or "",
        ),
        "expectedOut": lambda a: (
            a.expected_check_out_at is None,
            a.expected_check_out_at or timezone.now(),
            a.name or "",
        ),
        "lodging": lambda a: (a.lodging_stay_display or "", a.name or ""),
        "nights": lambda a: (a.lodging_nights, a.name or ""),
    }
    if sort_key in key_functions:
        filtered.sort(key=key_functions[sort_key], reverse=reverse)
    return filtered


def _night_count_expression(event: RetreatEvent):
    """집회 기간의 02:00~07:00 숙박 창과 겹치는 횟수를 계산한다."""
    expression = Value(0, output_field=IntegerField())
    current_date = event.start_date
    while current_date <= event.end_date:
        window_start = timezone.make_aware(datetime.combine(current_date, time(2, 0)))
        window_end = timezone.make_aware(datetime.combine(current_date, time(7, 0)))
        expression = expression + Case(
            When(
                expected_check_in_at__lt=window_end,
                expected_check_out_at__gt=window_start,
                then=Value(1),
            ),
            default=Value(0),
            output_field=IntegerField(),
        )
        current_date += timedelta(days=1)
    return expression


def _travel_filter_q(
    event: RetreatEvent,
    values: set[str],
    *,
    direction: str,
) -> Q:
    """교통 프리셋 ID·자차·미설정을 DB 시각 조건으로 변환한다."""
    if not values:
        return Q()
    presets = list(
        RetreatTravelPreset.objects.filter(
            event=event,
            direction=direction,
            is_active=True,
        ).order_by("sort_order", "id")
    )
    fixed, occurs_map = travel_fixed_and_occurs_map(presets)
    winning_ids = {preset.id for preset in occurs_map.values()}
    datetime_field = (
        "expected_check_in_at"
        if direction == RetreatTravelPreset.Direction.ARRIVAL
        else "expected_check_out_at"
    )
    custom_field = (
        "arrival_travel_is_custom"
        if direction == RetreatTravelPreset.Direction.ARRIVAL
        else "departure_travel_is_custom"
    )
    automatic_flag = Q(**{custom_field: False}) | Q(**{f"{custom_field}__isnull": True})
    fixed_time_q = Q(pk__in=[])
    selected_fixed_q = Q(pk__in=[])
    for preset in fixed:
        if preset.id not in winning_ids or preset.occurs_at is None:
            continue
        minute_start = preset.occurs_at.replace(second=0, microsecond=0)
        minute_end = minute_start + timedelta(minutes=1)
        time_q = Q(
            **{
                f"{datetime_field}__gte": minute_start,
                f"{datetime_field}__lt": minute_end,
            }
        )
        fixed_time_q |= time_q
        if str(preset.id) in values:
            selected_fixed_q |= automatic_flag & time_q

    result = selected_fixed_q
    if "__unset__" in values:
        result |= Q(**{f"{datetime_field}__isnull": True})
    if "__custom__" in values:
        result |= Q(**{f"{datetime_field}__isnull": False}) & (
            Q(**{custom_field: True}) | (automatic_flag & ~fixed_time_q)
        )
    return result


def filter_lodging_roster_queryset(
    qs: QuerySet,
    params,
    *,
    event: RetreatEvent,
) -> QuerySet | None:
    """DB에서 처리 가능한 명단 필터·정렬을 적용한다.

    전화번호 숫자 정규화 검색과 숙소 표시명 정렬은 기존 결과를 보존하기 위해
    Python fallback 경로로 돌려보낸다.
    """
    sort_key = str(params.get("sort", "") or "")
    if sort_key == "lodging":
        return None

    query = str(params.get("q", "") or "").strip()
    if query and re.search(r"\d", query):
        return None

    S = RetreatAttendee.CheckInStatus
    P = RetreatAttendee.ParticipationStatus
    nights = _csv_values(params, "nights")
    if nights or sort_key == "nights":
        qs = qs.annotate(_lodging_nights=_night_count_expression(event))
    if nights:
        night_q = Q(pk__in=[])
        if "0" in nights:
            night_q |= Q(_lodging_nights=0)
        if "1" in nights:
            night_q |= Q(_lodging_nights=1)
        if "2" in nights:
            night_q |= Q(_lodging_nights__gte=2)
        qs = qs.filter(night_q)

    arrivals = _csv_values(params, "arrivalTravel")
    if arrivals:
        qs = qs.filter(
            _travel_filter_q(
                event,
                arrivals,
                direction=RetreatTravelPreset.Direction.ARRIVAL,
            )
        )
    departures = _csv_values(params, "departureTravel")
    if departures:
        qs = qs.filter(
            _travel_filter_q(
                event,
                departures,
                direction=RetreatTravelPreset.Direction.DEPARTURE,
            )
        )

    statuses = _csv_values(params, "status")
    if statuses:
        qs = qs.filter(_effective_status__in=statuses)

    lodging_stays = _csv_values(params, "lodgingStay")
    if not lodging_stays:
        legacy_stay = _csv_values(params, "stay")
        legacy_assign = _csv_values(params, "assign")
        legacy_lodging = _csv_values(params, "lodging")
        if "eligible" in legacy_stay or "eligible" in legacy_lodging:
            lodging_stays.update({"active", "unassigned"})
        if legacy_stay.intersection(
            {"ineligible", "na"}
        ) or legacy_lodging.intersection({"ineligible", "na"}):
            lodging_stays.update({"ended", "no_stay", "absent"})
        if "assigned" in legacy_assign or "assigned" in legacy_lodging:
            lodging_stays.add("active")
        if "unassigned" in legacy_assign or "unassigned" in legacy_lodging:
            lodging_stays.add("unassigned")
    if lodging_stays:
        participating = Q(participation_status=P.PARTICIPATING)
        not_checked_out = ~Q(_effective_status=S.CHECKED_OUT)
        lodging_q = Q(pk__in=[])
        if "active" in lodging_stays:
            lodging_q |= (
                participating
                & not_checked_out
                & Q(
                    expected_check_in_at__isnull=False,
                    lodging_room__isnull=False,
                )
            )
        if "unassigned" in lodging_stays:
            lodging_q |= (
                participating
                & not_checked_out
                & Q(
                    expected_check_in_at__isnull=False,
                    lodging_room__isnull=True,
                )
            )
        if "ended" in lodging_stays:
            lodging_q |= participating & Q(_effective_status=S.CHECKED_OUT)
        if "no_stay" in lodging_stays:
            lodging_q |= (
                participating & not_checked_out & Q(expected_check_in_at__isnull=True)
            )
        if "absent" in lodging_stays:
            lodging_q |= Q(participation_status=P.ABSENT)
        qs = qs.filter(lodging_q)

    genders = _csv_values(params, "gender")
    if genders:
        qs = qs.filter(
            gender__in=["" if value == "__unset__" else value for value in genders]
        )

    regions = _csv_values(params, "region")
    if regions:
        qs = qs.filter(
            Q(group__region__name__in=regions)
            | Q(group__extra_scopes__region__name__in=regions)
        )
    divisions = _csv_values(params, "division")
    if divisions:
        qs = qs.filter(
            Q(group__division__name__in=divisions)
            | Q(group__extra_scopes__division__name__in=divisions)
        )
    if regions or divisions:
        qs = qs.distinct()

    if "1" in _csv_values(params, "memo"):
        qs = qs.exclude(memo="")
    if query:
        qs = qs.filter(name__icontains=query)

    date_from = _range_datetime(params.get("dateFrom", ""))
    date_to = _range_datetime(params.get("dateTo", ""))
    if date_from or date_to:
        qs = qs.filter(
            expected_check_in_at__isnull=False,
            expected_check_out_at__isnull=False,
        )
        if date_from:
            qs = qs.filter(expected_check_out_at__gte=date_from)
        if date_to:
            qs = qs.filter(expected_check_in_at__lte=date_to)

    reverse = str(params.get("dir", "asc") or "") == "desc"
    prefix = "-" if reverse else ""
    role_order = Case(
        When(member_role=RetreatAttendee.MemberRole.LEADER, then=Value(0)),
        When(member_role=RetreatAttendee.MemberRole.VICE_LEADER, then=Value(1)),
        When(member_role=RetreatAttendee.MemberRole.TEACHER, then=Value(2)),
        When(member_role=RetreatAttendee.MemberRole.MEMBER, then=Value(3)),
        default=Value(99),
        output_field=IntegerField(),
    )
    status_order = Case(
        When(_effective_status=S.PENDING, then=Value(0)),
        When(_effective_status=S.CHECKED_IN, then=Value(1)),
        When(_effective_status=S.CHECKED_OUT, then=Value(2)),
        default=Value(99),
        output_field=IntegerField(),
    )
    sort_fields = {
        "group": ("group__name", "name", "id"),
        "name": ("name", "id"),
        "expectedIn": ("expected_check_in_at", "name", "id"),
        "expectedOut": ("expected_check_out_at", "name", "id"),
    }
    if sort_key == "role":
        qs = qs.annotate(_role_order=role_order).order_by(
            f"{prefix}_role_order", f"{prefix}name", f"{prefix}id"
        )
    elif sort_key == "status":
        qs = qs.annotate(_status_order=status_order).order_by(
            f"{prefix}_status_order", f"{prefix}name", f"{prefix}id"
        )
    elif sort_key == "nights":
        qs = qs.order_by(f"{prefix}_lodging_nights", f"{prefix}name", f"{prefix}id")
    elif sort_key in sort_fields:
        qs = qs.order_by(*(f"{prefix}{field}" for field in sort_fields[sort_key]))
    return qs


def lodging_roster_summary(attendees: list[RetreatAttendee]) -> LodgingRosterSummary:
    s = RetreatAttendee.CheckInStatus
    p = RetreatAttendee.ParticipationStatus
    participating = [a for a in attendees if is_participating(a)]
    return LodgingRosterSummary(
        count_total=len(attendees),
        count_participating=len(participating),
        count_absent=sum(1 for a in attendees if a.participation_status == p.ABSENT),
        count_pending=sum(1 for a in participating if a.check_in_status == s.PENDING),
        count_checked_in=sum(
            1 for a in participating if a.check_in_status == s.CHECKED_IN
        ),
        count_checked_out=sum(
            1 for a in participating if a.check_in_status == s.CHECKED_OUT
        ),
        count_lodging_eligible=sum(1 for a in attendees if is_lodging_eligible(a)),
        count_lodging_unassigned=sum(
            1 for a in attendees if a.lodging_scope == "unassigned"
        ),
    )


def is_lodging_eligible(attendee: RetreatAttendee) -> bool:
    return is_lodging_stay_eligible(attendee)


def lodging_eligible_filter(qs: QuerySet) -> QuerySet:
    """숙박 대상만 — lodging_stay_status active|unassigned."""
    return lodging_stay_eligible_filter(qs)


def attendee_lodging_scope(attendee: RetreatAttendee) -> str:
    """레거시·집계용: eligible | assigned | unassigned | na."""
    S = RetreatAttendee.LodgingStayStatus
    status = attendee.lodging_stay_status
    if status in (S.ACTIVE, S.UNASSIGNED):
        return "assigned" if status == S.ACTIVE else "unassigned"
    return "na"


def attendee_lodging_eligible_key(attendee: RetreatAttendee) -> str:
    """필터용 숙박 여부: eligible | ineligible."""
    return "eligible" if is_lodging_eligible(attendee) else "ineligible"


def attendee_lodging_assignment_key(attendee: RetreatAttendee) -> str:
    """필터용 호실 배정: assigned | unassigned | '' (숙박 비대상)."""
    S = RetreatAttendee.LodgingStayStatus
    status = attendee.lodging_stay_status
    if status == S.ACTIVE:
        return "assigned"
    if status == S.UNASSIGNED:
        return "unassigned"
    return ""


def attendee_lodging_cell_label(attendee: RetreatAttendee) -> str | None:
    """숙소·호수 컬럼 라벨. 호실 표시(active) 시 None."""
    S = RetreatAttendee.LodgingStayStatus
    status = attendee.lodging_stay_status
    if status == S.ACTIVE:
        return None
    if status in (S.UNASSIGNED, S.ENDED, S.NO_STAY, S.ABSENT):
        return lodging_stay_display(attendee)
    return lodging_stay_display(attendee)


def lodging_night_count(attendee: RetreatAttendee) -> int:
    """예정 체류 구간과 매일 02:00~07:00가 겹치는 날짜 수."""
    starts_at = attendee.expected_check_in_at
    ends_at = attendee.expected_check_out_at
    if starts_at is None or ends_at is None or ends_at <= starts_at:
        return 0

    local_start = timezone.localtime(starts_at)
    local_end = timezone.localtime(ends_at)
    current_date = local_start.date()
    last_date = local_end.date()
    nights = 0
    while current_date <= last_date:
        window_start = timezone.make_aware(datetime.combine(current_date, time(2, 0)))
        window_end = timezone.make_aware(datetime.combine(current_date, time(7, 0)))
        if local_start < window_end and local_end > window_start:
            nights += 1
        current_date += timedelta(days=1)
    return nights


def lodging_roster_queryset(event: RetreatEvent, user: User) -> QuerySet:
    """권한 범위 명단의 공통 QuerySet.

    QuerySet 상태로 반환해 Paginator가 SQL LIMIT/OFFSET을 적용할 수 있게 한다.
    """
    visible_group_ids = list(
        visible_retreat_groups_for(user, event).values_list("id", flat=True)
    )
    check_in_order = Case(
        When(_effective_status=RetreatAttendee.CheckInStatus.CHECKED_IN, then=Value(0)),
        When(_effective_status=RetreatAttendee.CheckInStatus.PENDING, then=Value(1)),
        When(
            _effective_status=RetreatAttendee.CheckInStatus.CHECKED_OUT, then=Value(2)
        ),
        default=Value(3),
        output_field=IntegerField(),
    )
    return (
        visible_attendees_for(
            user,
            RetreatAttendee.objects.filter(group_id__in=visible_group_ids),
        )
        .select_related(
            "group",
            "group__region",
            "group__division",
            "lodging_room",
            "lodging_room__lodging",
            "user",
            "user__profile",
        )
        .prefetch_related(
            "group__extra_scopes__region",
            "group__extra_scopes__division",
        )
        .annotate(_effective_status=effective_status_expression())
        .order_by(
            check_in_order,
            "group__order",
            "group__id",
            "sort_order",
            "name",
            "id",
        )
    )


def lodging_roster_summary_for_queryset(qs: QuerySet) -> LodgingRosterSummary:
    """전체 객체를 만들지 않고 DB 집계로 명단 요약을 계산한다."""
    S = RetreatAttendee.CheckInStatus
    P = RetreatAttendee.ParticipationStatus
    participating = Q(participation_status=P.PARTICIPATING)
    eligible = (
        participating
        & ~Q(_effective_status=S.CHECKED_OUT)
        & Q(expected_check_in_at__isnull=False)
    )
    counts = qs.aggregate(
        count_total=Count("id"),
        count_participating=Count("id", filter=participating),
        count_absent=Count("id", filter=Q(participation_status=P.ABSENT)),
        count_pending=Count(
            "id", filter=participating & Q(_effective_status=S.PENDING)
        ),
        count_checked_in=Count(
            "id", filter=participating & Q(_effective_status=S.CHECKED_IN)
        ),
        count_checked_out=Count(
            "id", filter=participating & Q(_effective_status=S.CHECKED_OUT)
        ),
        count_lodging_eligible=Count("id", filter=eligible),
        count_lodging_unassigned=Count(
            "id", filter=eligible & Q(lodging_room__isnull=True)
        ),
    )
    return LodgingRosterSummary(**counts)


def _enrich_lodging_roster_attendees(
    attendees: list[RetreatAttendee],
    event: RetreatEvent,
    user: User,
    *,
    travel_presets: list[RetreatTravelPreset] | None = None,
) -> dict:
    """조회된 현재 페이지 조원에 화면 표시용 계산값을 붙인다."""
    if travel_presets is None:
        travel_presets = list(
            RetreatTravelPreset.objects.filter(event=event, is_active=True).order_by(
                "direction", "sort_order", "id"
            )
        )
    travel_presets = list(travel_presets)
    arrival_fixed, arrival_occurs = travel_fixed_and_occurs_map(
        [
            p
            for p in travel_presets
            if p.direction == RetreatTravelPreset.Direction.ARRIVAL
        ]
    )
    departure_fixed, departure_occurs = travel_fixed_and_occurs_map(
        [
            p
            for p in travel_presets
            if p.direction == RetreatTravelPreset.Direction.DEPARTURE
        ]
    )
    can_change_status = (
        user.is_superuser or effective_capabilities(user, event).change_check_in
    )
    for attendee in attendees:
        group_scopes = [
            (attendee.group.region.name, attendee.group.division.name),
            *[
                (scope.region.name, scope.division.name)
                for scope in attendee.group.extra_scopes.all()
            ],
        ]
        attendee.group_region_names = list(
            dict.fromkeys(region_name for region_name, _ in group_scopes)
        )
        attendee.group_division_names = list(
            dict.fromkeys(division_name for _, division_name in group_scopes)
        )
        attendee.group_scope_labels = [
            f"{region_name} · {division_name}"
            for region_name, division_name in dict.fromkeys(group_scopes)
        ]
        attendee.check_in_status = effective_status(attendee)
        attendee.lodging_stay_status = resolve_lodging_stay_status(attendee)
        attendee.lodging_scope = attendee_lodging_scope(attendee)
        attendee.lodging_eligible_key = attendee_lodging_eligible_key(attendee)
        attendee.lodging_assignment_key = attendee_lodging_assignment_key(attendee)
        attendee.lodging_cell_label = attendee_lodging_cell_label(attendee)
        attendee.lodging_stay_display = lodging_stay_display(attendee)
        attendee.lodging_nights = (
            attendee._lodging_nights
            if hasattr(attendee, "_lodging_nights")
            else lodging_night_count(attendee)
        )
        attendee.lodging_nights_label = (
            f"{attendee.lodging_nights}박" if attendee.lodging_nights > 0 else "숙박 X"
        )
        attendee.profile_locked = is_attendee_profile_locked(attendee)
        attendee.expected_timestamps_locked = attendee.profile_locked
        attendee.expected_check_in_locked = attendee.profile_locked
        attendee.expected_check_out_locked = (
            attendee.profile_locked and not can_change_status
        )
        attendee.arrival_travel_key = str(
            travel_bucket_key(
                attendee.expected_check_in_at,
                arrival_occurs,
                is_custom=attendee.arrival_travel_is_custom,
            )
        )
        attendee.departure_travel_key = str(
            travel_bucket_key(
                attendee.expected_check_out_at,
                departure_occurs,
                is_custom=attendee.departure_travel_is_custom,
            )
        )

    return {
        "roster_attendees": attendees,
        "roster_arrival_travel_chips": travel_filter_chip_defs(arrival_fixed),
        "roster_departure_travel_chips": travel_filter_chip_defs(departure_fixed),
        "travel_presets": travel_presets_for_event(event),
        "roster_night_chips": [
            ("0", "숙박 X"),
            ("1", "1박"),
            ("2", "2박 이상"),
        ],
    }


def lodging_roster_scope_choices(event: RetreatEvent, user: User) -> tuple[list, list]:
    """명단 필터의 지역·부서 선택지를 조 개수 수준의 조회로 만든다."""
    groups = (
        visible_retreat_groups_for(user, event)
        .select_related("region", "division")
        .prefetch_related(
            "extra_scopes__region",
            "extra_scopes__division",
        )
    )
    regions: set[str] = set()
    divisions: set[str] = set()
    for group in groups:
        regions.add(group.region.name)
        divisions.add(group.division.name)
        for scope in group.extra_scopes.all():
            regions.add(scope.region.name)
            divisions.add(scope.division.name)
    return sorted(regions), sorted(divisions)


def build_lodging_roster_page_context(
    event: RetreatEvent,
    user: User,
    *,
    page_number=1,
    params=None,
) -> dict | None:
    """DB에서 처리 가능한 전체 명단 한 페이지를 직접 조회한다."""
    from django.core.paginator import Paginator

    qs = lodging_roster_queryset(event, user)
    if params is not None:
        qs = filter_lodging_roster_queryset(qs, params, event=event)
        if qs is None:
            return None
    summary = lodging_roster_summary_for_queryset(qs)
    paginator = Paginator(qs, LODGING_ROSTER_PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    attendees = list(page_obj.object_list)
    context = _enrich_lodging_roster_attendees(attendees, event, user)
    filter_regions, filter_divisions = lodging_roster_scope_choices(event, user)
    context.update(
        {
            "roster_summary": summary,
            "roster_page": page_obj,
            "roster_page_size": LODGING_ROSTER_PAGE_SIZE,
            "roster_has_attendees": summary.count_total > 0,
            "roster_filter_regions": filter_regions,
            "roster_filter_divisions": filter_divisions,
        }
    )
    return context


def build_lodging_roster_context(
    event: RetreatEvent,
    user: User,
) -> dict:
    """필터 계산이 필요한 전체 명단 컨텍스트."""
    attendees = list(lodging_roster_queryset(event, user))
    context = _enrich_lodging_roster_attendees(attendees, event, user)
    filter_regions, filter_divisions = lodging_roster_scope_choices(event, user)
    context["roster_summary"] = lodging_roster_summary(attendees)
    context["roster_filter_regions"] = filter_regions
    context["roster_filter_divisions"] = filter_divisions
    return context
