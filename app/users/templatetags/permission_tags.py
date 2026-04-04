from __future__ import annotations

from django import template

from users.permissions import (
    can_access_counseling_manage_tab,
    can_access_counseling_tab,
    can_access_member_registry,
    can_access_parking_tab,
    can_access_team_roster_tab,
    is_parking_manager,
)
from users.services.user_display import user_display_name as resolve_user_display_name

register = template.Library()


@register.filter(name="can_access_registry_tab")
def can_access_registry_tab(user):
    return can_access_member_registry(user)


@register.filter(name="can_access_attendance_tab")
def can_access_attendance_tab(user):
    """탭 출석부: 팀장·셀장(직급 또는 기능 직책) 또는 목사·전도사·회장·부회장·총무·출석관리·운영."""
    return bool(user and can_access_team_roster_tab(user))


@register.filter(name="can_access_parking_tab")
def can_access_parking_tab_filter(user):
    return can_access_parking_tab(user)


@register.filter(name="can_access_parking_admin_tab")
def can_access_parking_admin_tab(user):
    return is_parking_manager(user)


@register.filter(name="user_display_name")
def user_display_name(user):
    return resolve_user_display_name(user)


@register.filter(name="can_access_counseling_tab")
def can_access_counseling_tab_filter(user):
    return can_access_counseling_tab(user)


@register.filter(name="can_access_counseling_manage_tab")
def can_access_counseling_manage_tab_filter(user):
    return can_access_counseling_manage_tab(user)


@register.filter(name="lookup_user_label")
def lookup_user_label(mapping, user_id):
    """컨텍스트의 user_id → 표시명 맵 조회 (가입 승인 등 일괄 로딩용)."""
    if not mapping or user_id is None:
        return ""
    try:
        key = int(user_id)
    except (TypeError, ValueError):
        key = user_id
    return mapping.get(key) or mapping.get(str(key)) or ""
