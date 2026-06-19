"""사용자 프로필 이미지 표시 URL."""

from __future__ import annotations

from django.templatetags.static import static

from users.models import User


def user_profile_avatar_url(user: User | None) -> str:
    """사용자 업로드 프로필 이미지 URL. 없으면 기본 아바타 static URL."""
    if user is None or not getattr(user, "is_authenticated", False):
        return static("attendance/default-avatar.svg")
    try:
        profile = user.profile
    except Exception:
        return static("attendance/default-avatar.svg")
    if (
        getattr(profile, "avatar_user_uploaded", False)
        and profile.avatar
        and getattr(profile.avatar, "name", "")
    ):
        return profile.avatar.url
    return static("attendance/default-avatar.svg")


def user_profile_avatar_api_value(user: User | None) -> str:
    """API 응답용 아바타 URL. 사용자 업로드가 없으면 빈 문자열."""
    if user is None or not getattr(user, "is_authenticated", False):
        return ""
    try:
        profile = user.profile
    except Exception:
        return ""
    if (
        getattr(profile, "avatar_user_uploaded", False)
        and profile.avatar
        and getattr(profile.avatar, "name", "")
    ):
        return profile.avatar.url
    return ""
