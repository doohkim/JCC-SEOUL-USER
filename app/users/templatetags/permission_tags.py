from __future__ import annotations

from django import template

register = template.Library()


@register.filter(name="can_access_registry_tab")
def can_access_registry_tab(user):
    """좌측 '교적부' 탭 — 목사·전도사(및 슈퍼유저)만."""
    from users.permissions import can_access_member_registry

    return can_access_member_registry(user)


@register.filter(name="can_manage_division_accounts_tab")
def can_manage_division_accounts_tab(user):
    """좌측 '계정관리' 탭 — 스태프·계정 관리 기능권한."""
    from users.permissions import can_manage_division_accounts

    return bool(user and can_manage_division_accounts(user))


@register.filter(name="can_access_onboarding_approvals_tab")
def can_access_onboarding_approvals_tab(user):
    """계정관리 내 '승인 절차' 탭 — 스태프·계정 관리 기능권한."""
    from users.permissions import can_access_onboarding_approvals

    return bool(user and can_access_onboarding_approvals(user))


@register.filter(name="can_access_attendance_tab")
def can_access_attendance_tab(user):
    """탭 출석부: 팀장·셀장(직급 또는 기능 직책) 또는 목사·전도사·회장·부회장·총무·출석관리·운영."""
    from users.permissions import can_access_team_roster_tab

    return bool(user and can_access_team_roster_tab(user))


@register.filter(name="can_access_parking_tab")
def can_access_parking_tab_filter(user):
    from users.permissions import can_access_parking_tab

    return can_access_parking_tab(user)


@register.filter(name="can_access_parking_admin_tab")
def can_access_parking_admin_tab(user):
    from users.permissions import is_parking_manager

    return is_parking_manager(user)


@register.filter(name="user_display_name")
def user_display_name(user):
    from users.services.user_display import (
        user_display_name as resolve_user_display_name,
    )

    return resolve_user_display_name(user)


@register.filter(name="user_org_summary")
def user_org_summary(user):
    """좌측 네비 프로필 보조 라인 — '지역 · 부서 · 팀 · 직급'.

    - 주 소속(`is_primary`) UserDivisionTeam 1개를 우선, 없으면 sort_order 순.
    - 비어 있는 부분(팀 미배정·직급 미설정 등)은 생략.
    - 익명 사용자에게는 빈 문자열을 돌려준다.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return ""
    udt = (
        user.division_teams.select_related(
            "division", "division__region", "team"
        )
        .order_by("-is_primary", "sort_order", "division__sort_order", "id")
        .first()
    )
    parts: list[str] = []
    if udt:
        region = getattr(udt.division, "region", None)
        if region and getattr(region, "name", ""):
            parts.append(region.name)
        if getattr(udt.division, "name", ""):
            parts.append(udt.division.name)
        if udt.team and getattr(udt.team, "name", ""):
            parts.append(udt.team.name)
    role = getattr(user, "role_level", None)
    if role and getattr(role, "name", ""):
        parts.append(role.name)
    return " · ".join(parts)


@register.filter(name="can_access_counseling_tab")
def can_access_counseling_tab_filter(user):
    from users.permissions import can_access_counseling_tab

    return can_access_counseling_tab(user)


@register.filter(name="can_access_counseling_manage_tab")
def can_access_counseling_manage_tab_filter(user):
    from users.permissions import can_access_counseling_manage_tab

    return can_access_counseling_manage_tab(user)


@register.filter(name="can_access_retreat_tab")
def can_access_retreat_tab_filter(user):
    """좌측 '수련회' 탭 — 조장/부조장 또는 운영진(staff)·회장단·슈퍼유저."""
    from users.permissions import can_access_retreat_tab

    return can_access_retreat_tab(user)


@register.filter(name="is_retreat_council_any")
def is_retreat_council_any_filter(user):
    """수련회 회장단(어떤 행사든) 여부 — 좌측 탭/UI 노출용."""
    from users.permissions import is_retreat_council_any

    return is_retreat_council_any(user)


@register.filter(name="can_access_notices_tab")
def can_access_notices_tab(user):
    """좌측 '공지사항'(하위 타임테이블 포함) — 로그인한 모든 참가자."""
    from users.permissions import can_access_notices_tab as can_access_notices

    return bool(user and can_access_notices(user))


@register.filter(name="can_access_pastoral_tab")
def can_access_pastoral_tab(user):
    """좌측 '대시보드·출석부·교적부' 탭 — 슈퍼유저 또는 목사·전도사."""
    from users.permissions import can_access_pastoral_tab as can_access_pastoral

    return bool(user and can_access_pastoral(user))


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
