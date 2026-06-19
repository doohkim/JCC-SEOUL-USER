"""숙소·호수 관리 페이지 요약 집계."""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Count, Q, QuerySet

from retreat.models import Lodging, LodgingRoom, RetreatAttendee, RetreatEvent
from retreat.services.participation import participating_filter

_ACTIVE_ATTENDEE = ~Q(attendees__check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT)


@dataclass(frozen=True)
class LodgingFacilitySummary:
    lodging_count: int
    room_count: int
    capacity_finite_total: int
    assignment_rate_pct: float | None
    assigned_active: int
    unassigned_eligible: int
    rooms_remaining: int
    assigned_pending: int


@dataclass(frozen=True)
class LodgingPageSummary:
    facility: LodgingFacilitySummary


def _lodging_eligible_qs(event: RetreatEvent) -> QuerySet[RetreatAttendee]:
    """숙박 관리 대상: 참석 + 예상 입실 시각 있음 + 입실전·입실만 (퇴실 제외)."""
    return participating_filter(
        RetreatAttendee.objects.filter(
            group__event=event,
            expected_check_in_at__isnull=False,
        )
    ).exclude(check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT)


def _rooms_qs(event: RetreatEvent) -> QuerySet[LodgingRoom]:
    return LodgingRoom.objects.filter(lodging__event=event).annotate(
        assigned_count=Count(
            "attendees",
            filter=_ACTIVE_ATTENDEE,
        )
    )


def build_lodging_page_summary(event: RetreatEvent) -> LodgingPageSummary:
    """집회 전체 숙소·호수 관리 요약."""
    rooms = list(_rooms_qs(event))
    eligible_qs = _lodging_eligible_qs(event)

    lodging_count = Lodging.objects.filter(event=event).count()
    room_count = len(rooms)
    capacity_finite_total = sum(r.capacity for r in rooms if r.capacity > 0)

    assigned_active = eligible_qs.filter(lodging_room__isnull=False).count()
    unassigned_eligible = eligible_qs.filter(lodging_room__isnull=True).count()
    assignment_rate_pct = (
        round(assigned_active / capacity_finite_total * 100, 1)
        if capacity_finite_total > 0
        else None
    )
    rooms_remaining = sum(
        1 for r in rooms if r.capacity == 0 or r.assigned_count < r.capacity
    )

    S = RetreatAttendee.CheckInStatus
    assigned_pending = eligible_qs.filter(
        lodging_room__isnull=False,
        check_in_status=S.PENDING,
    ).count()

    facility = LodgingFacilitySummary(
        lodging_count=lodging_count,
        room_count=room_count,
        capacity_finite_total=capacity_finite_total,
        assignment_rate_pct=assignment_rate_pct,
        assigned_active=assigned_active,
        unassigned_eligible=unassigned_eligible,
        rooms_remaining=rooms_remaining,
        assigned_pending=assigned_pending,
    )
    return LodgingPageSummary(facility=facility)
