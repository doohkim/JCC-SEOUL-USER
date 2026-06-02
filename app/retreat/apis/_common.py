"""retreat API 공통 헬퍼 — 객체 조회 + 권한 게이트."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from retreat.models import RetreatEvent, RetreatGroup
from users.permissions import (
    is_retreat_council,
    is_retreat_group_leader,
    is_retreat_staff,
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
    - staff OK (본인 region/division)
    """
    if user.is_superuser:
        return
    if is_retreat_group_leader(user, group):
        return
    if is_retreat_staff(user, group.event):
        # staff 도 본인 region/division 한정 여부는 visible 결과로 확인.
        if group.id in set(
            visible_retreat_groups_for(user, group.event).values_list("id", flat=True)
        ):
            return
    raise PermissionDenied("이 조의 정보를 변경할 권한이 없습니다.")


def user_can_edit_attendee_timestamps(user, group: RetreatGroup) -> bool:
    """입실/퇴실 시각 직접 수정 — staff·회장단·슈퍼유저만."""
    if user.is_superuser:
        return True
    if is_retreat_council(user, group.event):
        return True
    return is_retreat_staff(user, group.event)


def user_can_manage_lodging(user, event: RetreatEvent) -> bool:
    """숙소/호실 CRUD — staff·회장단·슈퍼유저만."""
    if user.is_superuser:
        return True
    if is_retreat_council(user, event):
        return True
    return is_retreat_staff(user, event)


def assert_can_manage_lodging(user, event: RetreatEvent) -> None:
    if not user_can_manage_lodging(user, event):
        raise PermissionDenied("숙소 관리 권한이 없습니다.")


def user_can_view_event(user, event: RetreatEvent) -> bool:
    """행사 가시 권한 — 본인이 볼 수 있는 그룹이 하나라도 이 행사에 속하면 OK."""
    if user.is_superuser:
        return True
    if is_retreat_council(user, event):
        return True
    if is_retreat_staff(user, event):
        return True
    return visible_retreat_groups_for(user, event).exists()


def assert_can_view_event(user, event: RetreatEvent) -> None:
    if not user_can_view_event(user, event):
        raise PermissionDenied("이 행사를 볼 권한이 없습니다.")
