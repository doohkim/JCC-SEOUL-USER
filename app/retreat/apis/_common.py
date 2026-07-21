"""retreat API 공통 헬퍼 — 객체 조회 + 권한 게이트."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from retreat.models import RetreatEvent, RetreatGroup
from retreat.services.staff_capabilities import effective_capabilities
from users.permissions import (
    can_add_retreat_group,
    can_change_retreat_check_in,
    can_delete_checked_out_attendee,
    can_link_attendee_user,
    can_manage_retreat_group_leaders,
    is_retreat_event_admin,
    is_retreat_group_leader,
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
    """조 정보 변경 권한."""
    caps = effective_capabilities(user, group.event)
    if user.is_superuser or caps.edit_group:
        return
    if is_retreat_group_leader(user, group):
        return
    raise PermissionDenied("이 조의 정보를 변경할 권한이 없습니다.")


def user_can_edit_attendee_timestamps(user, group: RetreatGroup) -> bool:
    """입실/퇴실 시각 직접 수정 — 프로필 수정 권한 또는 집회 전체 관리자."""
    if user.is_superuser:
        return True
    caps = effective_capabilities(user, group.event)
    if caps.edit_attendee_profile:
        return True
    return is_retreat_event_admin(user, group.event)


def user_can_manage_lodging(user, event: RetreatEvent) -> bool:
    """숙소/호실 CRUD."""
    if user.is_superuser:
        return True
    return effective_capabilities(user, event).manage_lodging_rooms


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
    """숙소 탭·API 조회."""
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
    """조원 프로필(이름·연락처 등) 수정."""
    if user.is_superuser:
        return True
    caps = effective_capabilities(user, group.event)
    if caps.edit_attendee_profile:
        return True
    return is_retreat_group_leader(user, group)


def assert_can_edit_attendee_details(user, group: RetreatGroup) -> None:
    if not user_can_edit_attendee_details(user, group):
        raise PermissionDenied("조원 정보를 수정할 권한이 없습니다.")


def assert_can_link_attendee_user(user, group: RetreatGroup) -> None:
    if not can_link_attendee_user(user, group.event):
        raise PermissionDenied("사용자 계정 연동 권한이 없습니다.")


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
    """퇴실 조원 PATCH 시 차단할 프로필 키."""
    from retreat.services.check_in_stamps import is_attendee_profile_locked

    if not is_attendee_profile_locked(attendee):
        return frozenset()
    if (
        user
        and group
        and (
            getattr(user, "is_superuser", False)
            or can_change_retreat_check_in(user, group.event)
        )
    ):
        return _PROFILE_LOCKED_PATCH_KEYS - _COUNCIL_CHECKED_OUT_PATCH_KEYS
    return _PROFILE_LOCKED_PATCH_KEYS


def user_can_delete_attendee(user, group: RetreatGroup, attendee=None) -> bool:
    """조원 삭제."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if attendee is not None and attendee.user_id and attendee.user_id == user.id:
        # 본인 연동 행은 조원 명단에서 삭제 불가 (조 운영진 해제 경로 사용)
        return False
    if attendee is not None:
        from retreat.services.check_in_stamps import is_attendee_profile_locked

        if is_attendee_profile_locked(attendee):
            return can_delete_checked_out_attendee(user, group.event)
    caps = effective_capabilities(user, group.event)
    if caps.delete_attendee:
        return True
    return is_retreat_group_leader(user, group)


_SELF_ATTENDEE_DELETE_DENIED = (
    "본인 조원 행은 삭제할 수 없습니다. " "본인 해제는 관리 > 조 운영진에서 처리하세요."
)


def assert_can_delete_attendee(user, group: RetreatGroup, attendee=None) -> None:
    if (
        attendee is not None
        and attendee.user_id
        and user
        and attendee.user_id == user.id
    ):
        raise PermissionDenied(_SELF_ATTENDEE_DELETE_DENIED)
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
    """입퇴실 상태 전환 규칙."""
    if previous == new:
        return
    from retreat.models import RetreatAttendee

    pending = RetreatAttendee.CheckInStatus.PENDING
    checked_in = RetreatAttendee.CheckInStatus.CHECKED_IN
    checked_out = RetreatAttendee.CheckInStatus.CHECKED_OUT

    if new == pending and previous in (checked_in, checked_out):
        if not (user.is_superuser or can_change_retreat_check_in(user, group.event)):
            raise PermissionDenied("입실·퇴실 후 입실전으로 되돌릴 수 없습니다.")


def sanitize_attendee_patch_keys(user, group: RetreatGroup, payload: dict) -> dict:
    """권한에 따라 허용되지 않는 조원 PATCH 키를 제거."""
    caps = effective_capabilities(user, group.event)
    cleaned = dict(payload)
    if not can_change_retreat_check_in(user, group.event):
        for key in _CHECK_IN_STATUS_KEYS:
            cleaned.pop(key, None)
    if not can_link_attendee_user(user, group.event):
        cleaned.pop("user", None)
    if not caps.edit_attendee_profile and not user.is_superuser:
        for key in _ATTENDEE_DETAIL_PATCH_KEYS:
            cleaned.pop(key, None)
    return cleaned
