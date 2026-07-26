"""조원 명단 정렬·조 카드 조장 표시 우선순위."""

from __future__ import annotations

from typing import Iterable

from django.db.models import Case, F, IntegerField, QuerySet, Value, When

from retreat.models import RetreatAttendee, RetreatGroupMembership
from users.services.user_display import user_display_name

_CHECK_IN_SORT = {
    RetreatAttendee.CheckInStatus.CHECKED_IN: 0,
    RetreatAttendee.CheckInStatus.PENDING: 1,
    RetreatAttendee.CheckInStatus.CHECKED_OUT: 2,
}


def attendee_check_in_sort_annotation() -> Case:
    return Case(
        When(_effective_status=RetreatAttendee.CheckInStatus.CHECKED_IN, then=Value(0)),
        When(_effective_status=RetreatAttendee.CheckInStatus.PENDING, then=Value(1)),
        When(
            _effective_status=RetreatAttendee.CheckInStatus.CHECKED_OUT, then=Value(2)
        ),
        default=Value(3),
        output_field=IntegerField(),
    )


def attendee_role_sort_annotation() -> Case:
    return Case(
        When(member_role=RetreatAttendee.MemberRole.LEADER, then=Value(0)),
        When(member_role=RetreatAttendee.MemberRole.VICE_LEADER, then=Value(1)),
        When(member_role=RetreatAttendee.MemberRole.TEACHER, then=Value(2)),
        default=Value(3),
        output_field=IntegerField(),
    )


def order_attendees_for_member_list(qs: QuerySet) -> QuerySet:
    """조원 명단 기본 정렬: 입실상태 → 역할 → 입실 시각 → 등록 순."""
    from retreat.services.effective_check_in import effective_status_expression

    return qs.annotate(
        _effective_status=effective_status_expression(),
        _check_in_sort=attendee_check_in_sort_annotation(),
        _role_sort=attendee_role_sort_annotation(),
    ).order_by(
        "_check_in_sort",
        "_role_sort",
        F("checked_in_at").asc(nulls_last=True),
        "sort_order",
        "name",
        "id",
    )


def pick_group_card_leader_name(leaders: Iterable[RetreatAttendee]) -> str:
    """조 카드에 표시할 조장 이름 1명 (소속 명단 기준).

    1. 입실 > 입실전 (퇴실 제외)
    2. 사용자 계정이 연동된 조장
    3. 가장 먼저 등록된 조장 (id 오름차순)
    """
    from retreat.services.effective_check_in import effective_status

    candidates = [
        leader
        for leader in leaders
        if effective_status(leader) != RetreatAttendee.CheckInStatus.CHECKED_OUT
        and (leader.name or "").strip()
    ]
    if not candidates:
        return ""

    def rank(leader: RetreatAttendee) -> tuple[int, int, int]:
        return (
            _CHECK_IN_SORT.get(effective_status(leader), 99),
            0 if leader.user_id else 1,
            leader.id,
        )

    best = min(candidates, key=rank)
    return (best.name or "").strip()


def pick_group_card_leader_name_from_memberships(
    memberships: Iterable[RetreatGroupMembership],
) -> str:
    """소속 명단에 조장이 없을 때(겸직 담당조 등) membership 조장 이름.

    ``role=leader`` 만 대상. 여러 명이면 가장 먼저 배정된 순(id).
    """
    leaders = [
        m
        for m in memberships
        if m.role == RetreatGroupMembership.Role.LEADER and m.user_id
    ]
    if not leaders:
        return ""
    best = min(leaders, key=lambda m: m.id)
    return (user_display_name(best.user) or "").strip()


def resolve_group_card_leader_name(
    attendee_leaders: Iterable[RetreatAttendee],
    memberships: Iterable[RetreatGroupMembership] | None = None,
) -> str:
    """조 카드 조장 표시: 소속 명단 조장 우선, 없으면 운영진 membership."""
    name = pick_group_card_leader_name(attendee_leaders)
    if name:
        return name
    if memberships is None:
        return ""
    return pick_group_card_leader_name_from_memberships(memberships)
