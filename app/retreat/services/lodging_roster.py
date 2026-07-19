"""숙소 탭 전체 명단 — 집계·조회."""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db.models import Case, IntegerField, QuerySet, Value, When

from retreat.models import RetreatAttendee, RetreatEvent
from retreat.services.check_in_stamps import (
    is_attendee_profile_locked,
    is_expected_check_in_locked,
    is_expected_check_out_locked,
    is_expected_timestamps_locked,
)
from retreat.services.lodging_stay import (
    is_lodging_stay_eligible,
    lodging_stay_display,
    lodging_stay_eligible_filter,
)
from retreat.services.participation import is_participating
from retreat.services.account_retired import visible_attendees_for
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


def build_lodging_roster_context(
    event: RetreatEvent,
    user: User,
) -> dict:
    """전체 명단 페이지 컨텍스트 — visible 조 범위 내 조원만."""
    visible_group_ids = list(
        visible_retreat_groups_for(user, event).values_list("id", flat=True)
    )
    check_in_order = Case(
        When(
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN,
            then=Value(0),
        ),
        When(
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
            then=Value(1),
        ),
        When(
            check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT,
            then=Value(2),
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
        .order_by(
            check_in_order,
            "group__order",
            "group__id",
            "sort_order",
            "name",
            "id",
        )
    )
    for attendee in attendees:
        attendee.lodging_scope = attendee_lodging_scope(attendee)
        attendee.lodging_eligible_key = attendee_lodging_eligible_key(attendee)
        attendee.lodging_assignment_key = attendee_lodging_assignment_key(attendee)
        attendee.lodging_cell_label = attendee_lodging_cell_label(attendee)
        attendee.lodging_stay_display = lodging_stay_display(attendee)
        attendee.expected_timestamps_locked = is_expected_timestamps_locked(attendee)
        attendee.profile_locked = is_attendee_profile_locked(attendee)
        attendee.expected_check_in_locked = is_expected_check_in_locked(
            attendee, user, attendee.group
        )
        attendee.expected_check_out_locked = is_expected_check_out_locked(
            attendee, user, attendee.group
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
