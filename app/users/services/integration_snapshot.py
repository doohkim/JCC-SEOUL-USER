"""연동 API용 유저 권한·프로필 스냅샷."""

from __future__ import annotations

from typing import Any

from users.models import User
from users.permissions import (
    can_access_attendance_roster,
    can_access_member_registry,
    can_access_team_roster_tab,
    can_manage_division_accounts,
    is_attendance_manager,
    is_parking_manager,
    is_platform_admin,
    registry_divisions_for,
    visible_divisions_for,
)


def user_permission_snapshot(user: User) -> dict[str, Any]:
    """외부 서버가 권한 판단에 쓸 수 있는 요약(비밀번호 등 제외)."""
    rl = getattr(user, "role_level", None)
    role = None
    if rl is not None:
        role = {
            "id": rl.id,
            "code": getattr(rl, "code", None),
            "name": getattr(rl, "name", None),
            "level": getattr(rl, "level", None),
        }

    div_vis = list(visible_divisions_for(user).values_list("code", flat=True))
    div_reg = list(registry_divisions_for(user).values_list("code", flat=True))

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email or "",
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "role_level": role,
        "flags": {
            "can_manage_attendance": bool(getattr(user, "can_manage_attendance", False)),
            "can_manage_accounts": bool(getattr(user, "can_manage_accounts", False)),
            "can_manage_parking": bool(getattr(user, "can_manage_parking", False)),
        },
        "access": {
            "platform_admin": is_platform_admin(user),
            "attendance_manager": is_attendance_manager(user),
            "parking_manager": is_parking_manager(user),
            "account_management": can_manage_division_accounts(user),
            "member_registry": can_access_member_registry(user),
            "team_roster_tab": can_access_team_roster_tab(user),
            "attendance_roster": can_access_attendance_roster(user),
        },
        "divisions": {
            "dashboard_visible_codes": div_vis,
            "registry_scope_codes": div_reg,
        },
    }


def user_profile_snapshot(user: User) -> dict[str, Any]:
    """프로필(표시 이름·전화 등) — 연동 서버에 넘길 최소 필드."""
    out: dict[str, Any] = {
        "id": user.id,
        "username": user.username,
        "email": user.email or "",
    }
    try:
        p = user.profile
        out["display_name"] = getattr(p, "display_name", "") or ""
        out["phone"] = getattr(p, "phone", "") or ""
    except Exception:
        out["display_name"] = ""
        out["phone"] = ""
    return out


def build_integration_user_body(user: User) -> dict[str, Any]:
    """연동 API 응답용 단일 유저 객체."""
    return {
        **user_profile_snapshot(user),
        "authorization": user_permission_snapshot(user),
    }
