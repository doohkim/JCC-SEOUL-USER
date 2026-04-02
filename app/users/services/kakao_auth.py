"""카카오 OAuth 로그인 사용자 생성/갱신 파이프라인."""

from __future__ import annotations

import hashlib
import mimetypes
import logging
from urllib.request import urlopen

from django.core.files.base import ContentFile
from django.contrib.auth import get_user_model

from users.models import UserProfile, UserProfileAvatar

logger = logging.getLogger(__name__)


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


def _extract_kakao_profile_image_urls(details: dict, kwargs: dict) -> list[str]:
    """
    카카오 로그인 응답에서 프로필 이미지 URL들을 추출한다.

    - 카카오는 보통 1개지만, 서로 다른 해상도/키가 오면 여러 개를 누적 저장할 수 있게 목록으로 받는다.
    """
    out: list[str] = []

    def push(v) -> None:
        if v and isinstance(v, str):
            s = v.strip()
            if s and s not in out:
                out.append(s)
        elif isinstance(v, list):
            for x in v:
                push(x)

    # details에 직접 들어오는 경우(일부 설정/파이프라인 조합)
    for k in (
        "profile_image",
        "profile_image_url",
        "thumbnail_image_url",
        "picture",
        "avatar",
    ):
        push(details.get(k))

    response = kwargs.get("response") or {}
    if not isinstance(response, dict):
        return out

    props = response.get("properties") or {}
    if isinstance(props, dict):
        for k in ("profile_image", "profile_image_url", "thumbnail_image_url", "picture"):
            push(props.get(k))

    account = response.get("kakao_account") or {}
    if isinstance(account, dict):
        profile = account.get("profile") or {}
        if isinstance(profile, dict):
            for k in (
                "profile_image_url",
                "thumbnail_image_url",
                "profile_image",
                "picture",
            ):
                push(profile.get(k))

    return out


def _download_image_bytes(url: str) -> tuple[bytes, str] | None:
    if not url or not isinstance(url, str):
        return None

    try:
        with urlopen(url, timeout=10) as resp:
            data = resp.read()
            content_type = resp.headers.get("Content-Type", "") or ""
    except Exception:
        return None

    # 확장자 추정(없으면 기본 jpg)
    ext = ""
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ""
    if not ext:
        base = url.split("?")[0]
        _, dot, last = base.rpartition(".")
        ext = f".{last}" if dot and last else ".jpg"

    return data, ext


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
    image_urls = _extract_kakao_profile_image_urls(details, kwargs)
    logger.info(
        "kakao_auth: uid=%s nickname_present=%s image_url_present=%s",
        uid,
        bool(nickname),
        bool(image_urls),
    )

    if user is not None:
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={"onboarding_status": UserProfile.OnboardingStatus.PENDING},
        )
        changed_fields: list[str] = []
        if nickname and profile.display_name != nickname:
            profile.display_name = nickname
            changed_fields.append("display_name")
        new_avatar_content_hash: str | None = None
        saved_hashes: list[str] = []
        for image_url in image_urls:
            downloaded = _download_image_bytes(image_url)
            if not downloaded:
                continue
            data, ext = downloaded
            content_hash = hashlib.sha256(data).hexdigest()

            if UserProfileAvatar.objects.filter(
                user_profile=profile, content_hash=content_hash
            ).exists():
                continue

            history = UserProfileAvatar(
                user_profile=profile,
                source_url=image_url,
                content_hash=content_hash,
            )
            content_for_history = ContentFile(
                data, name=f"user_{user.id}_avatar_{content_hash[:10]}{ext}"
            )
            history.image.save(content_for_history.name, content_for_history, save=False)
            history.save()
            new_avatar_content_hash = content_hash
            saved_hashes.append(content_hash)

        if new_avatar_content_hash:
            latest = (
                profile.avatar_history.order_by("-created_at")
                .filter(content_hash=new_avatar_content_hash)
                .first()
            )
            if latest and latest.image:
                profile.avatar = latest.image
                changed_fields.append("avatar")
        if saved_hashes:
            logger.info(
                "kakao_auth: uid=%s avatar_history_saved=%d last_hash_prefix=%s",
                user.id,
                len(saved_hashes),
                new_avatar_content_hash[:10] if new_avatar_content_hash else "",
            )

        if changed_fields:
            # auto_now 필드를 함께 갱신하려고 updated_at도 포함
            changed_fields.append("updated_at")
            profile.save(update_fields=changed_fields)
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

        new_avatar_content_hash: str | None = None
        saved_hashes: list[str] = []
        for image_url in image_urls:
            downloaded = _download_image_bytes(image_url)
            if not downloaded:
                continue
            data, ext = downloaded
            content_hash = hashlib.sha256(data).hexdigest()

            if UserProfileAvatar.objects.filter(
                user_profile=profile, content_hash=content_hash
            ).exists():
                continue

            history = UserProfileAvatar(
                user_profile=profile,
                source_url=image_url,
                content_hash=content_hash,
            )
            content_for_history = ContentFile(
                data, name=f"user_{existing.id}_avatar_{content_hash[:10]}{ext}"
            )
            history.image.save(content_for_history.name, content_for_history, save=False)
            history.save()
            new_avatar_content_hash = content_hash
            saved_hashes.append(content_hash)

        if new_avatar_content_hash:
            latest = (
                profile.avatar_history.order_by("-created_at")
                .filter(content_hash=new_avatar_content_hash)
                .first()
            )
            if latest and latest.image:
                profile.avatar = latest.image

        if saved_hashes:
            logger.info(
                "kakao_auth: uid=%s avatar_history_saved=%d last_hash_prefix=%s",
                existing.id,
                len(saved_hashes),
                new_avatar_content_hash[:10] if new_avatar_content_hash else "",
            )
        profile.save(update_fields=["display_name", "avatar", "updated_at"])
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

    # 가입 직후 프로필 이미지가 있으면 히스토리에 누적 저장(새 이미지일 때만)
    new_avatar_content_hash: str | None = None
    saved_hashes: list[str] = []
    for image_url in image_urls:
        downloaded = _download_image_bytes(image_url)
        if not downloaded:
            continue
        data, ext = downloaded
        content_hash = hashlib.sha256(data).hexdigest()

        if UserProfileAvatar.objects.filter(
            user_profile=profile, content_hash=content_hash
        ).exists():
            continue

        history = UserProfileAvatar(
            user_profile=profile,
            source_url=image_url,
            content_hash=content_hash,
        )
        content_for_history = ContentFile(
            data, name=f"user_{created.id}_avatar_{content_hash[:10]}{ext}"
        )
        history.image.save(content_for_history.name, content_for_history, save=False)
        history.save()
        new_avatar_content_hash = content_hash
        saved_hashes.append(content_hash)

    if new_avatar_content_hash:
        latest = (
            profile.avatar_history.order_by("-created_at")
            .filter(content_hash=new_avatar_content_hash)
            .first()
        )
        if latest and latest.image:
            profile.avatar = latest.image
            profile.save(update_fields=["avatar", "updated_at"])
    if saved_hashes:
        logger.info(
            "kakao_auth: uid=%s avatar_history_saved=%d last_hash_prefix=%s",
            created.id,
            len(saved_hashes),
            new_avatar_content_hash[:10] if new_avatar_content_hash else "",
        )
    return {"user": created}
