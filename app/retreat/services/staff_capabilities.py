"""집회 운영진 역할별 capability 정책 (단일 진실).

역할 추가 시 ``ROLE_POLICIES`` 에 정책 함수 1개만 등록한다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import TYPE_CHECKING, Callable

from django.db.models import Q, QuerySet

if TYPE_CHECKING:
    from users.models import User

    from retreat.models import RetreatCouncilMembership, RetreatEvent


class AccessLevel(Enum):
    NONE = 0
    VIEW = 1
    MUTATE = 2

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, AccessLevel):
            return NotImplemented
        return self.value >= other.value

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, AccessLevel):
            return NotImplemented
        return self.value < other.value

    def __le__(self, other: object) -> bool:
        if not isinstance(other, AccessLevel):
            return NotImplemented
        return self.value <= other.value

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, AccessLevel):
            return NotImplemented
        return self.value > other.value

    @staticmethod
    def max_of(*levels: AccessLevel) -> AccessLevel:
        return max(levels, key=lambda level: level.value)


@dataclass(frozen=True)
class StaffScope:
    """조회·변경 대상 그룹/데이터 범위."""

    kind: str  # event | region | division | none
    region_id: int | None = None
    division_id: int | None = None

    @classmethod
    def event_wide(cls) -> StaffScope:
        return cls(kind="event")

    @classmethod
    def none(cls) -> StaffScope:
        return cls(kind="none")

    @classmethod
    def for_region(cls, region_id: int) -> StaffScope:
        return cls(kind="region", region_id=region_id)

    @classmethod
    def for_division(cls, division_id: int, *, region_id: int | None) -> StaffScope:
        return cls(
            kind="division",
            division_id=division_id,
            region_id=region_id,
        )

    def merge(self, other: StaffScope) -> StaffScope:
        rank = {"none": 0, "division": 1, "region": 2, "event": 3}
        if rank.get(other.kind, 0) > rank.get(self.kind, 0):
            return other
        if other.kind == self.kind == "event":
            return self
        if other.kind == self.kind == "region" and (
            self.region_id == other.region_id
        ):
            return self
        if other.kind == self.kind == "division" and (
            self.division_id == other.division_id
        ):
            return self
        if self.kind == "event" or other.kind == "event":
            return StaffScope.event_wide()
        return self


@dataclass(frozen=True)
class RetreatCapabilities:
    dashboard: AccessLevel = AccessLevel.NONE
    groups: AccessLevel = AccessLevel.NONE
    pickup: AccessLevel = AccessLevel.NONE
    lodging: AccessLevel = AccessLevel.NONE
    admin: AccessLevel = AccessLevel.NONE

    add_group: bool = False
    edit_group: bool = False
    delete_group: bool = False
    add_attendee: bool = False
    edit_attendee_profile: bool = False
    link_attendee_user: bool = False
    change_check_in: bool = False
    delete_attendee: bool = False
    delete_checked_out_attendee: bool = False

    pickup_overview: AccessLevel = AccessLevel.NONE
    pickup_arrival: AccessLevel = AccessLevel.NONE
    pickup_departure: AccessLevel = AccessLevel.NONE
    pickup_select_group: bool = False
    delete_pickup: bool = False

    manage_lodging_rooms: bool = False
    edit_lodging_roster: bool = False

    manage_staff: bool = False
    view_staff: bool = False
    manage_timetable: bool = False
    view_changelog: bool = False

    scope: StaffScope = StaffScope.none()

    def merge(self, other: RetreatCapabilities) -> RetreatCapabilities:
        """더 넓은 권한(합집합)을 반환."""
        return RetreatCapabilities(
            dashboard=AccessLevel.max_of(self.dashboard, other.dashboard),
            groups=AccessLevel.max_of(self.groups, other.groups),
            pickup=AccessLevel.max_of(self.pickup, other.pickup),
            lodging=AccessLevel.max_of(self.lodging, other.lodging),
            admin=AccessLevel.max_of(self.admin, other.admin),
            add_group=self.add_group or other.add_group,
            edit_group=self.edit_group or other.edit_group,
            delete_group=self.delete_group or other.delete_group,
            add_attendee=self.add_attendee or other.add_attendee,
            edit_attendee_profile=(
                self.edit_attendee_profile or other.edit_attendee_profile
            ),
            link_attendee_user=self.link_attendee_user or other.link_attendee_user,
            change_check_in=self.change_check_in or other.change_check_in,
            delete_attendee=self.delete_attendee or other.delete_attendee,
            delete_checked_out_attendee=(
                self.delete_checked_out_attendee
                or other.delete_checked_out_attendee
            ),
            pickup_overview=AccessLevel.max_of(
                self.pickup_overview, other.pickup_overview
            ),
            pickup_arrival=AccessLevel.max_of(
                self.pickup_arrival, other.pickup_arrival
            ),
            pickup_departure=AccessLevel.max_of(
                self.pickup_departure, other.pickup_departure
            ),
            pickup_select_group=self.pickup_select_group or other.pickup_select_group,
            delete_pickup=self.delete_pickup or other.delete_pickup,
            manage_lodging_rooms=self.manage_lodging_rooms or other.manage_lodging_rooms,
            edit_lodging_roster=self.edit_lodging_roster or other.edit_lodging_roster,
            manage_staff=self.manage_staff or other.manage_staff,
            view_staff=self.view_staff or other.view_staff,
            manage_timetable=self.manage_timetable or other.manage_timetable,
            view_changelog=self.view_changelog or other.view_changelog,
            scope=self.scope.merge(other.scope),
        )


NONE_CAPS = RetreatCapabilities()


def _event_admin_caps() -> RetreatCapabilities:
    return RetreatCapabilities(
        dashboard=AccessLevel.VIEW,
        groups=AccessLevel.MUTATE,
        pickup=AccessLevel.VIEW,
        lodging=AccessLevel.MUTATE,
        admin=AccessLevel.MUTATE,
        add_group=True,
        edit_group=True,
        delete_group=True,
        add_attendee=True,
        edit_attendee_profile=True,
        link_attendee_user=True,
        change_check_in=True,
        delete_attendee=True,
        delete_checked_out_attendee=False,
        pickup_overview=AccessLevel.MUTATE,
        pickup_arrival=AccessLevel.MUTATE,
        pickup_departure=AccessLevel.MUTATE,
        pickup_select_group=True,
        delete_pickup=True,
        manage_lodging_rooms=True,
        edit_lodging_roster=True,
        manage_staff=True,
        view_staff=True,
        manage_timetable=True,
        view_changelog=True,
        scope=StaffScope.event_wide(),
    )


def _event_observer_caps() -> RetreatCapabilities:
    return RetreatCapabilities(
        dashboard=AccessLevel.VIEW,
        groups=AccessLevel.VIEW,
        pickup=AccessLevel.VIEW,
        lodging=AccessLevel.VIEW,
        pickup_overview=AccessLevel.VIEW,
        pickup_arrival=AccessLevel.VIEW,
        pickup_departure=AccessLevel.VIEW,
        scope=StaffScope.event_wide(),
    )


def _pickup_observer_caps() -> RetreatCapabilities:
    return RetreatCapabilities(
        pickup=AccessLevel.VIEW,
        pickup_overview=AccessLevel.VIEW,
        pickup_arrival=AccessLevel.VIEW,
        pickup_departure=AccessLevel.VIEW,
        scope=StaffScope.event_wide(),
    )


def _region_admin_caps(region_id: int) -> RetreatCapabilities:
    return RetreatCapabilities(
        dashboard=AccessLevel.VIEW,
        groups=AccessLevel.VIEW,
        pickup=AccessLevel.VIEW,
        add_attendee=True,
        edit_attendee_profile=True,
        pickup_overview=AccessLevel.VIEW,
        pickup_arrival=AccessLevel.MUTATE,
        pickup_departure=AccessLevel.MUTATE,
        pickup_select_group=True,
        scope=StaffScope.for_region(region_id),
    )


def _region_observer_caps(region_id: int) -> RetreatCapabilities:
    return RetreatCapabilities(
        dashboard=AccessLevel.VIEW,
        groups=AccessLevel.VIEW,
        pickup=AccessLevel.VIEW,
        pickup_overview=AccessLevel.VIEW,
        pickup_arrival=AccessLevel.VIEW,
        pickup_departure=AccessLevel.VIEW,
        scope=StaffScope.for_region(region_id),
    )


def _division_admin_caps(division_id: int, *, region_id: int | None) -> RetreatCapabilities:
    return RetreatCapabilities(
        dashboard=AccessLevel.VIEW,
        groups=AccessLevel.VIEW,
        pickup=AccessLevel.VIEW,
        add_attendee=True,
        edit_attendee_profile=True,
        pickup_overview=AccessLevel.VIEW,
        pickup_arrival=AccessLevel.MUTATE,
        pickup_departure=AccessLevel.MUTATE,
        pickup_select_group=True,
        scope=StaffScope.for_division(division_id, region_id=region_id),
    )


def _division_observer_caps(
    division_id: int, *, region_id: int | None
) -> RetreatCapabilities:
    return RetreatCapabilities(
        dashboard=AccessLevel.VIEW,
        groups=AccessLevel.VIEW,
        pickup=AccessLevel.VIEW,
        pickup_overview=AccessLevel.VIEW,
        pickup_arrival=AccessLevel.VIEW,
        pickup_departure=AccessLevel.VIEW,
        scope=StaffScope.for_division(division_id, region_id=region_id),
    )


def _leader_caps() -> RetreatCapabilities:
    """조장/부조장 — 본인 조만 (범위는 그룹 멤버십으로 별도 필터)."""
    return RetreatCapabilities(
        dashboard=AccessLevel.VIEW,
        groups=AccessLevel.VIEW,
        pickup=AccessLevel.MUTATE,
        add_attendee=True,
        edit_attendee_profile=True,
        delete_attendee=True,
        pickup_arrival=AccessLevel.MUTATE,
        pickup_departure=AccessLevel.MUTATE,
        delete_pickup=True,
        scope=StaffScope.none(),
    )


def _superuser_caps() -> RetreatCapabilities:
    caps = _event_admin_caps()
    return replace(caps, delete_checked_out_attendee=True)


def _caps_for_membership(membership: RetreatCouncilMembership) -> RetreatCapabilities:
    from retreat.models import RetreatCouncilMembership as M

    role = membership.role
    if role == M.Role.EVENT_ADMIN:
        return _event_admin_caps()
    if role == M.Role.EVENT_OBSERVER:
        return _event_observer_caps()
    if role == M.Role.PICKUP_OBSERVER:
        return _pickup_observer_caps()
    if role == M.Role.REGION_ADMIN:
        return _region_admin_caps(membership.region_id)
    if role == M.Role.REGION_OBSERVER:
        return _region_observer_caps(membership.region_id)
    if role == M.Role.DIVISION_ADMIN:
        region_id = membership.region_id
        if region_id is None and membership.division_id:
            region_id = membership.division.region_id
        return _division_admin_caps(membership.division_id, region_id=region_id)
    if role == M.Role.DIVISION_OBSERVER:
        region_id = membership.region_id
        if region_id is None and membership.division_id:
            region_id = membership.division.region_id
        return _division_observer_caps(membership.division_id, region_id=region_id)
    return NONE_CAPS


def staff_capabilities(user: User, event: RetreatEvent | None) -> RetreatCapabilities | None:
    if not user or not getattr(user, "is_authenticated", False) or event is None:
        return None
    if user.is_superuser:
        return _superuser_caps()
    membership = (
        user.retreat_council_memberships.filter(event=event)
        .select_related("region", "division", "division__region")
        .first()
    )
    if not membership:
        return None
    return _caps_for_membership(membership)


def leader_capabilities(user: User, event: RetreatEvent | None) -> RetreatCapabilities:
    if not user or not getattr(user, "is_authenticated", False) or event is None:
        return NONE_CAPS
    if user.retreat_group_memberships.filter(group__event=event).exists():
        return _leader_caps()
    return NONE_CAPS


def effective_capabilities(user: User, event: RetreatEvent | None) -> RetreatCapabilities:
    staff = staff_capabilities(user, event)
    leader = leader_capabilities(user, event)
    if staff is None:
        return leader
    return staff.merge(leader)


def get_staff_membership(user: User, event: RetreatEvent | None):
    if not user or not getattr(user, "is_authenticated", False) or event is None:
        return None
    return (
        user.retreat_council_memberships.filter(event=event)
        .select_related("region", "division", "division__region")
        .first()
    )


def is_pickup_observer_with_leader(user: User, event: RetreatEvent | None) -> bool:
    """픽업 담당 관찰자 + 조장/부조장 겸직."""
    from retreat.models import RetreatCouncilMembership as M

    membership = get_staff_membership(user, event)
    if membership is None or membership.role != M.Role.PICKUP_OBSERVER:
        return False
    if event is None:
        return False
    return user.retreat_group_memberships.filter(group__event=event).exists()


def has_event_wide_pickup_view(user: User, event: RetreatEvent | None) -> bool:
    """픽업 화면 — 집회 전체 조 조회 (pickup_observer·event_observer·event_admin 등)."""
    staff = staff_capabilities(user, event)
    if staff is None:
        return False
    return staff.pickup >= AccessLevel.VIEW and staff.scope.kind == "event"


def _leader_group_ids(user: User, event: RetreatEvent) -> list[int]:
    return list(
        user.retreat_group_memberships.filter(group__event=event).values_list(
            "group_id", flat=True
        )
    )


def scope_filter_q(scope: StaffScope, *, prefix: str = "") -> Q:
    field = f"{prefix}__" if prefix else ""
    if scope.kind == "event":
        return Q()
    if scope.kind == "region" and scope.region_id:
        return Q(**{f"{field}region_id": scope.region_id})
    if scope.kind == "division" and scope.division_id:
        return Q(**{f"{field}division_id": scope.division_id})
    return Q(pk__in=[])


def visible_groups_qs(user: User, event: RetreatEvent) -> QuerySet:
    from retreat.models import RetreatGroup

    caps = effective_capabilities(user, event)
    base = RetreatGroup.objects.filter(event=event)
    if is_pickup_observer_with_leader(user, event):
        leader_ids = _leader_group_ids(user, event)
        if leader_ids:
            return base.filter(pk__in=leader_ids)
        return base.none()
    if caps.scope.kind == "event":
        if caps.groups >= AccessLevel.VIEW:
            return base
        return base.none()
    if caps.groups == AccessLevel.NONE and caps.scope.kind == "none":
        leader_ids = _leader_group_ids(user, event)
        if leader_ids:
            return base.filter(pk__in=leader_ids)
        return base.none()
    q = scope_filter_q(caps.scope)
    scoped = base.filter(q)
    leader_ids = _leader_group_ids(user, event)
    if leader_ids:
        return scoped | base.filter(pk__in=leader_ids)
    return scoped


def can_access_retreat_page(user: User, event: RetreatEvent, page: str) -> bool:
    if page == "admin":
        from users.permissions import can_access_retreat_admin

        return can_access_retreat_admin(user, event)
    caps = effective_capabilities(user, event)
    mapping = {
        "dashboard": caps.dashboard,
        "groups": caps.groups,
        "pickup": caps.pickup,
        "lodging": caps.lodging,
    }
    level = mapping.get(page, AccessLevel.NONE)
    return level >= AccessLevel.VIEW


def pickup_tab_access_level(
    caps: RetreatCapabilities, tab: str
) -> AccessLevel:
    if tab == "overview":
        return caps.pickup_overview
    if tab in ("arrival", "입회"):
        return caps.pickup_arrival
    if tab in ("departure", "출회"):
        return caps.pickup_departure
    return caps.pickup


def assert_pickup_mutate(caps: RetreatCapabilities, tab: str) -> bool:
    return pickup_tab_access_level(caps, tab) >= AccessLevel.MUTATE
