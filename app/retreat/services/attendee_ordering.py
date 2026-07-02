"""조원 명단 정렬·조 카드 조장 표시 우선순위."""

from __future__ import annotations

from typing import Iterable

from django.db.models import Case, F, IntegerField, QuerySet, Value, When

from retreat.models import RetreatAttendee

_CHECK_IN_SORT = {
    RetreatAttendee.CheckInStatus.CHECKED_IN: 0,
    RetreatAttendee.CheckInStatus.PENDING: 1,
    RetreatAttendee.CheckInStatus.CHECKED_OUT: 2,
}


def attendee_check_in_sort_annotation() -> Case:
    return Case(
        When(check_in_status=RetreatAttendee.CheckInStatus.CHECKED_IN, then=Value(0)),
        When(check_in_status=RetreatAttendee.CheckInStatus.PENDING, then=Value(1)),
        When(check_in_status=RetreatAttendee.CheckInStatus.CHECKED_OUT, then=Value(2)),
        default=Value(3),
        output_field=IntegerField(),
    )


def attendee_role_sort_annotation() -> Case:
    return Case(
        When(member_role=RetreatAttendee.MemberRole.LEADER, then=Value(0)),
        When(member_role=RetreatAttendee.MemberRole.VICE_LEADER, then=Value(1)),
        default=Value(2),
        output_field=IntegerField(),
    )


def order_attendees_for_member_list(qs: QuerySet) -> QuerySet:
    """조원 명단 기본 정렬: 입실상태 → 역할 → 입실 시각 → 등록 순."""
    return qs.annotate(
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
    """조 카드에 표시할 조장 이름 1명.

    1. 입실 > 입실전 (퇴실 제외)
    2. 사용자 계정이 연동된 조장
    3. 가장 먼저 등록된 조장 (id 오름차순)
    """
    candidates = [
        leader
        for leader in leaders
        if leader.check_in_status != RetreatAttendee.CheckInStatus.CHECKED_OUT
        and (leader.name or "").strip()
    ]
    if not candidates:
        return ""

    def rank(leader: RetreatAttendee) -> tuple[int, int, int]:
        return (
            _CHECK_IN_SORT.get(leader.check_in_status, 99),
            0 if leader.user_id else 1,
            leader.id,
        )

    best = min(candidates, key=rank)
    return (best.name or "").strip()
