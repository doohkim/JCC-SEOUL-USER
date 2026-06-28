"""retreat API 공통 헬퍼 — 객체 조회 + 권한 게이트."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from retreat.models import RetreatEvent, RetreatGroup
from users.permissions import (
    can_add_retreat_group,
    can_change_retreat_check_in,
    can_manage_retreat_group_leaders,
    is_retreat_council,
    is_retreat_group_leader,
    is_retreat_pastoral_observer,
    visible_retreat_groups_for,
)


def get_group_or_403(user, group_id: int) -> RetreatGroup:
    """그룹 조회 + 가시 권한 확인. 권한 없으면 403."""

    group = get_object_or_404(RetreatGroup, pk=group_id)
    visible_ids = set(
        visible_retreat_groups_for(user, group.event).values_list("id", flat=True)
    )
    if group.id not in visible_ids:
        raise PermissionDenied("이 조의 정보를 볼 권한이 없습니다.")
    return group


def assert_can_mutate_group(user, group: RetreatGroup) -> None:
    """수정/추가/삭제 등 변경 권한.

    - 슈퍼유저 OK
    - 조장/부조장 OK (본인 그룹)
    - 회장단 OK
    - 목사·전도사(회장단 제외)는 변경 불가
    """
    if is_retreat_pastoral_observer(user, group.event):
        raise PermissionDenied("목사·전도사는 조 정보를 열람만 할 수 있습니다.")
    if user.is_superuser:
        return
    if is_retreat_group_leader(user, group):
        return
    if is_retreat_council(user, group.event):
        return
    raise PermissionDenied("이 조의 정보를 변경할 권한이 없습니다.")


def user_can_edit_attendee_timestamps(user, group: RetreatGroup) -> bool:
    """입실/퇴실 시각 직접 수정 — 회장단·슈퍼유저만."""
    if user.is_superuser:
        return True
    return is_retreat_council(user, group.event)


def user_can_manage_lodging(user, event: RetreatEvent) -> bool:
    """숙소/호실 CRUD — 회장단·슈퍼유저만."""
    if user.is_superuser:
        return True
    return is_retreat_council(user, event)


def assert_can_manage_lodging(user, event: RetreatEvent) -> None:
    if not user_can_manage_lodging(user, event):
        raise PermissionDenied("숙소 관리 권한이 없습니다.")


def user_can_view_event(user, event: RetreatEvent) -> bool:
    """집회 가시 권한 — 본인이 볼 수 있는 그룹이 하나라도 이 집회에 속하면 OK."""
    if user.is_superuser:
        return True
    return visible_retreat_groups_for(user, event).exists()


def assert_can_view_event(user, event: RetreatEvent) -> None:
    if not user_can_view_event(user, event):
        raise PermissionDenied("이 집회를 볼 권한이 없습니다.")


def assert_can_view_lodging(user, event: RetreatEvent) -> None:
    """숙소 탭·API 조회 — 슈퍼유저·해당 집회 회장단만 (조장·부조장 제외)."""
    from users.permissions import can_view_retreat_all

    if not can_view_retreat_all(user, event):
        raise PermissionDenied("이 집회의 숙소를 볼 권한이 없습니다.")


def assert_can_add_group(user, event: RetreatEvent) -> None:
    if not can_add_retreat_group(user, event):
        raise PermissionDenied("조를 추가할 권한이 없습니다.")


def assert_can_manage_group_leaders(user, group: RetreatGroup) -> None:
    if not can_manage_retreat_group_leaders(user, group):
        raise PermissionDenied("조 운영진을 변경할 권한이 없습니다.")


def user_can_edit_attendee_details(user, group: RetreatGroup) -> bool:
    """조원 프로필(이름·연락처 등) 수정 — 슈퍼유저·회장단·본인 조 조장/부조장."""
    if is_retreat_pastoral_observer(user, group.event):
        return False
    if user.is_superuser:
        return True
    if is_retreat_council(user, group.event):
        return True
    return is_retreat_group_leader(user, group)


def assert_can_edit_attendee_details(user, group: RetreatGroup) -> None:
    if not user_can_edit_attendee_details(user, group):
        raise PermissionDenied("조원 정보를 수정할 권한이 없습니다.")


def assert_can_change_check_in_status(user, group: RetreatGroup) -> None:
    if not can_change_retreat_check_in(user, group.event):
        raise PermissionDenied("입·퇴실 상태를 변경할 권한이 없습니다.")


_PROFILE_LOCKED_PATCH_KEYS = frozenset(
    {
        "name",
        "phone",
        "gender",
        "memo",
        "member_role",
        "user",
        "expected_check_in_at",
        "expected_check_out_at",
        "lodging_room",
        "participation_status",
    }
)

_COUNCIL_CHECKED_OUT_PATCH_KEYS = frozenset({"expected_check_out_at"})


def profile_locked_patch_keys_for(user, group: RetreatGroup, attendee) -> frozenset:
    """퇴실 조원 PATCH 시 차단할 프로필 키 (회장단·슈퍼유저 예외 반영)."""
    from retreat.services.check_in_stamps import is_attendee_profile_locked

    if not is_attendee_profile_locked(attendee):
        return _PROFILE_LOCKED_PATCH_KEYS
    if user and group and (
        getattr(user, "is_superuser", False)
        or is_retreat_council(user, group.event)
    ):
        return _PROFILE_LOCKED_PATCH_KEYS - _COUNCIL_CHECKED_OUT_PATCH_KEYS
    return _PROFILE_LOCKED_PATCH_KEYS


def user_can_delete_attendee(user, group: RetreatGroup, attendee=None) -> bool:
    """조원 삭제 — 슈퍼유저·회장단·본인 조 조장/부조장 (퇴실은 회장단·슈퍼유저만)."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if is_retreat_pastoral_observer(user, group.event):
        return False
    if attendee is not None:
        from retreat.services.check_in_stamps import is_attendee_profile_locked

        if is_attendee_profile_locked(attendee):
            if user.is_superuser:
                return True
            return is_retreat_council(user, group.event)
    if user.is_superuser:
        return True
    if is_retreat_council(user, group.event):
        return True
    return is_retreat_group_leader(user, group)


def assert_can_delete_attendee(user, group: RetreatGroup, attendee=None) -> None:
    if not user_can_delete_attendee(user, group, attendee=attendee):
        raise PermissionDenied("조원을 삭제할 권한이 없습니다.")


_PROFILE_PATCH_KEYS = frozenset(
    {"name", "phone", "gender", "memo", "member_role", "user"}
)

_ATTENDEE_DETAIL_PATCH_KEYS = frozenset(
    {
        "name",
        "phone",
        "gender",
        "memo",
        "member_role",
        "user",
        "expected_check_in_at",
        "expected_check_out_at",
        "lodging_room",
        "participation_status",
    }
)

_CHECK_IN_STATUS_KEYS = frozenset(
    {"check_in_status", "checked_in_at", "checked_out_at"}
)


def assert_check_in_status_transition(
    user,
    group: RetreatGroup,
    *,
    previous: str,
    new: str,
) -> None:
    """입퇴실 상태 전환 규칙 (회장단·슈퍼유저만 호출 전제)."""
    if previous == new:
        return
    from retreat.models import RetreatAttendee

    pending = RetreatAttendee.CheckInStatus.PENDING
    checked_in = RetreatAttendee.CheckInStatus.CHECKED_IN
    checked_out = RetreatAttendee.CheckInStatus.CHECKED_OUT

    if new == pending and previous in (checked_in, checked_out):
        if not (user.is_superuser or is_retreat_council(user, group.event)):
            raise PermissionDenied("입실·퇴실 후 입실전으로 되돌릴 수 없습니다.")
