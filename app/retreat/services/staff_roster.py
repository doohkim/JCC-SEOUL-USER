"""집회 운영진 명단 — 배정 규칙·중복 검증."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from retreat.models import (
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
)

if TYPE_CHECKING:
    from users.models import User

StaffAssignKind = Literal["council", "group"]


@dataclass(frozen=True)
class UserEventStaffSummary:
    council_membership: RetreatCouncilMembership | None
    group_membership: RetreatGroupMembership | None


def user_event_staff_summary(user, event: RetreatEvent) -> UserEventStaffSummary:
    council = (
        RetreatCouncilMembership.objects.filter(event=event, user=user)
        .select_related("region", "division")
        .first()
    )
    group_membership = (
        RetreatGroupMembership.objects.filter(user=user, group__event=event)
        .select_related("group")
        .order_by("group__order", "group__name", "id")
        .first()
    )
    return UserEventStaffSummary(
        council_membership=council,
        group_membership=group_membership,
    )


def user_assigned_to_event_staff(user, event: RetreatEvent) -> bool:
    summary = user_event_staff_summary(user, event)
    return bool(summary.council_membership or summary.group_membership)


def assert_can_assign_event_staff(
    user,
    event: RetreatEvent,
    *,
    kind: StaffAssignKind,
    group: RetreatGroup | None = None,
    exclude_council_id: int | None = None,
    exclude_group_membership_id: int | None = None,
) -> None:
    """집회당 집회운영 1건 + 조장·부조장 1개 조 (규칙 B)."""
    summary = user_event_staff_summary(user, event)

    if kind == "council":
        existing = summary.council_membership
        if (
            existing is not None
            and (exclude_council_id is None or existing.id != exclude_council_id)
        ):
            raise ValueError("이 집회에 이미 집회 운영진 역할이 배정된 사용자입니다.")
        return

    if group is None:
        raise ValueError("조를 지정해야 합니다.")
    if group.event_id != event.id:
        raise ValueError("이 집회의 조가 아닙니다.")

    existing_group = summary.group_membership
    if existing_group is None:
        return
    if (
        exclude_group_membership_id is not None
        and existing_group.id == exclude_group_membership_id
    ):
        return
    if existing_group.group_id != group.id:
        raise ValueError("이 집회에 이미 다른 조 운영진으로 배정된 사용자입니다.")
