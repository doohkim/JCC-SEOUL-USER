"""사용자 표시 이름: 프로필 → 카카오 extra_data → username."""

from __future__ import annotations

import re
from collections.abc import Iterable

from django.contrib.auth import get_user_model

from social_django.models import UserSocialAuth

User = get_user_model()


def extract_kakao_nickname_from_extra(extra) -> str:
    if not isinstance(extra, dict):
        return ""
    props = extra.get("properties") or {}
    if isinstance(props, dict):
        nick = (props.get("nickname") or "").strip()
        if nick:
            return nick
    account = extra.get("kakao_account") or {}
    if isinstance(account, dict):
        profile = account.get("profile") or {}
        if isinstance(profile, dict):
            nick = (profile.get("nickname") or "").strip()
            if nick:
                return nick
    return ""


def kakao_nickname_map_for_user_ids(user_ids: Iterable[int]) -> dict[int, str]:
    ids = [int(x) for x in user_ids if x is not None]
    if not ids:
        return {}
    out: dict[int, str] = {}
    for row in UserSocialAuth.objects.filter(user_id__in=ids, provider="kakao").values(
        "user_id", "extra_data"
    ):
        nick = extract_kakao_nickname_from_extra(row.get("extra_data") or {})
        if nick and row["user_id"] not in out:
            out[row["user_id"]] = nick
    return out


def user_display_name(user, *, kakao_map: dict[int, str] | None = None) -> str:
    """표시용 닉네임. 비로그인이면 빈 문자열, 없으면 username."""
    if user is None:
        return ""
    if not getattr(user, "is_authenticated", False):
        return ""
    try:
        profile = user.profile
        real = (profile.real_name or "").strip()
        if real:
            return real
        dn = (profile.display_name or "").strip()
        if dn:
            return dn
    except Exception:
        pass
    if kakao_map is not None:
        nick = kakao_map.get(user.pk, "")
        if nick:
            return nick
    else:
        extra = (
            UserSocialAuth.objects.filter(user_id=user.pk, provider="kakao")
            .values_list("extra_data", flat=True)
            .first()
        )
        nick = extract_kakao_nickname_from_extra(extra or {})
        if nick:
            return nick
    return (user.username or "").strip() or str(user.pk)


def _phone_suffix4(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-4:] if len(digits) >= 4 else ""


def user_account_link_label(user) -> str:
    """계정 연결 피커용: ``실명-휴대폰뒤4자리`` (예: 김도오-6804)."""
    if user is None:
        return ""
    profile = getattr(user, "profile", None)
    real = (getattr(profile, "real_name", "") or "").strip()
    suffix = _phone_suffix4(getattr(profile, "phone", "") or "")
    if real and suffix:
        return f"{real}-{suffix}"
    if real:
        return real
    if suffix:
        return suffix
    return user_display_name(user) or (user.username or "").strip() or str(user.pk)
