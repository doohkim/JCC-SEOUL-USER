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
from users.models import Division, Region

if TYPE_CHECKING:
    from users.models import User

StaffAssignKind = Literal["council", "group"]


class CouncilScopeError(ValueError):
    """council 역할·담당 범위 검증 실패 (field는 API ValidationError 키)."""

    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(message)


def resolve_council_staff_scope(
    role: str,
    *,
    region_id: int | None,
    division_id: int | None,
) -> tuple[int | None, int | None]:
    """council 역할에 맞는 region_id·division_id 반환."""
    if role in RetreatCouncilMembership.EVENT_WIDE_ROLES:
        if region_id or division_id:
            raise CouncilScopeError(
                "scope",
                "집회 전체·픽업 관찰 역할에는 담당 범위를 지정할 수 없습니다.",
            )
        return None, None
    if role in RetreatCouncilMembership.REGION_SCOPED_ROLES:
        if not region_id:
            raise CouncilScopeError("region", "지역 역할에는 담당 지역이 필요합니다.")
        if division_id:
            raise CouncilScopeError(
                "division", "지역 역할에는 부서를 지정할 수 없습니다."
            )
        if not Region.objects.filter(pk=region_id).exists():
            raise CouncilScopeError("region", "존재하지 않는 지역입니다.")
        return region_id, None
    if role in RetreatCouncilMembership.DIVISION_SCOPED_ROLES:
        if not division_id:
            raise CouncilScopeError("division", "부서 역할에는 담당 부서가 필요합니다.")
        division = Division.objects.filter(pk=division_id).select_related("region").first()
        if division is None:
            raise CouncilScopeError("division", "존재하지 않는 부서입니다.")
        if region_id and region_id != division.region_id:
            raise CouncilScopeError(
                "region", "담당 지역과 부서의 지역이 일치하지 않습니다."
            )
        return division.region_id, division_id
    raise CouncilScopeError("role", "올바르지 않은 역할입니다.")


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
