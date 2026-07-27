"""숙소 탭 전체 명단 — 집계·조회."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Case, IntegerField, QuerySet, Value, When
from django.utils import timezone

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


def build_lodging_roster_context(
    event: RetreatEvent,
    user: User,
) -> dict:
    """전체 명단 페이지 컨텍스트 — visible 조 범위 내 조원만."""
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
    attendees = list(
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
    travel_presets = list(
        RetreatTravelPreset.objects.filter(event=event, is_active=True).order_by(
            "direction", "sort_order", "id"
        )
    )
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
        attendee.lodging_nights = lodging_night_count(attendee)
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

    s = RetreatAttendee.CheckInStatus
    p = RetreatAttendee.ParticipationStatus
    count_absent = sum(1 for a in attendees if a.participation_status == p.ABSENT)
    participating = [a for a in attendees if is_participating(a)]
    count_pending = sum(1 for a in participating if a.check_in_status == s.PENDING)
    count_checked_in = sum(
        1 for a in participating if a.check_in_status == s.CHECKED_IN
    )
    count_checked_out = sum(
        1 for a in participating if a.check_in_status == s.CHECKED_OUT
    )
    count_lodging_eligible = sum(1 for a in attendees if is_lodging_eligible(a))
    count_lodging_unassigned = sum(
        1 for a in attendees if a.lodging_scope == "unassigned"
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
        "roster_summary": LodgingRosterSummary(
            count_total=len(attendees),
            count_participating=len(participating),
            count_absent=count_absent,
            count_pending=count_pending,
            count_checked_in=count_checked_in,
            count_checked_out=count_checked_out,
            count_lodging_eligible=count_lodging_eligible,
            count_lodging_unassigned=count_lodging_unassigned,
        ),
    }
