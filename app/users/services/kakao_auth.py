"""카카오 OAuth 로그인 사용자 생성/갱신 파이프라인."""

from __future__ import annotations

from django.contrib.auth import get_user_model

from users.models import UserProfile


def _build_username(uid: str) -> str:
    return f"kakao_{uid}"


def _extract_kakao_nickname(details: dict, kwargs: dict) -> str:
    nickname = (
        details.get("nickname")
        or details.get("fullname")
        or details.get("first_name")
        or ""
    )
    if nickname:
        return str(nickname).strip()
    response = kwargs.get("response") or {}
    if isinstance(response, dict):
        props = response.get("properties") or {}
        if isinstance(props, dict) and props.get("nickname"):
            return str(props.get("nickname")).strip()
        account = response.get("kakao_account") or {}
        if isinstance(account, dict):
            profile = account.get("profile") or {}
            if isinstance(profile, dict) and profile.get("nickname"):
                return str(profile.get("nickname")).strip()
    return ""


def create_or_update_kakao_user(
    strategy,
    backend,
    uid,
    details,
    user=None,
    *args,
    **kwargs,
):
    """카카오 최초 로그인 시 내부 사용자를 자동 생성한다."""
    if backend.name != "kakao":
        return {}

    nickname = _extract_kakao_nickname(details, kwargs)

    if user is not None:
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={"onboarding_status": UserProfile.OnboardingStatus.PENDING},
        )
        if nickname and profile.display_name != nickname:
            profile.display_name = nickname
            profile.save(update_fields=["display_name", "updated_at"])
        return {"user": user}

    UserModel = get_user_model()
    username = _build_username(str(uid))
    existing = UserModel.objects.filter(username=username).first()

    email = details.get("email", "")
    first_name = details.get("first_name", "")
    last_name = details.get("last_name", "")
    fullname = details.get("fullname", "")

    if existing:
        changed = False
        if email and not existing.email:
            existing.email = email
            changed = True
        if fullname and not existing.first_name and not existing.last_name:
            existing.first_name = fullname
            changed = True
        else:
            if first_name and not existing.first_name:
                existing.first_name = first_name
                changed = True
            if last_name and not existing.last_name:
                existing.last_name = last_name
                changed = True
        if changed:
            existing.save(update_fields=["email", "first_name", "last_name"])
        profile, _ = UserProfile.objects.get_or_create(
            user=existing,
            defaults={"onboarding_status": UserProfile.OnboardingStatus.PENDING},
        )
        if nickname and profile.display_name != nickname:
            profile.display_name = nickname
            profile.save(update_fields=["display_name", "updated_at"])
        return {"user": existing}

    created = UserModel.objects.create_user(
        username=username,
        email=email,
        first_name=first_name or fullname,
        last_name=last_name,
    )
    profile, _ = UserProfile.objects.get_or_create(
        user=created,
        defaults={"onboarding_status": UserProfile.OnboardingStatus.PENDING},
    )
    if nickname and profile.display_name != nickname:
        profile.display_name = nickname
        profile.save(update_fields=["display_name", "updated_at"])
    return {"user": created}
