"""iOS 등 모바일 클라이언트용 카카오 액세스 토큰 로그인."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.contrib.auth import get_user_model

from users.services.kakao_auth import create_or_update_kakao_user

logger = logging.getLogger(__name__)
User = get_user_model()


class KakaoMobileAuthError(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        self.message = message
        super().__init__(message or code)


@dataclass(frozen=True)
class KakaoMobileAuthResult:
    user: User
    token_key: str
    created: bool


class _KakaoBackendStub:
    name = "kakao"


def _fetch_kakao_profile(access_token: str) -> dict:
    req = Request(
        "https://kapi.kakao.com/v2/user/me",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        },
        method="GET",
    )
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        logger.warning("kakao_mobile_auth: http_error status=%s body=%s", exc.code, body[:300])
        if exc.code in (401, 403):
            raise KakaoMobileAuthError("invalid_kakao_token", "카카오 토큰이 유효하지 않습니다.") from exc
        raise KakaoMobileAuthError("kakao_api_error", "카카오 사용자 정보를 가져오지 못했습니다.") from exc
    except URLError as exc:
        logger.warning("kakao_mobile_auth: network_error %s", exc)
        raise KakaoMobileAuthError("kakao_network_error", "카카오 서버에 연결하지 못했습니다.") from exc
    except json.JSONDecodeError as exc:
        raise KakaoMobileAuthError("kakao_invalid_response", "카카오 응답을 해석하지 못했습니다.") from exc


def _details_from_kakao_response(payload: dict) -> dict:
    account = payload.get("kakao_account") or {}
    profile = account.get("profile") or {}
    props = payload.get("properties") or {}
    nickname = (
        profile.get("nickname")
        or props.get("nickname")
        or ""
    )
    return {
        "nickname": nickname,
        "email": account.get("email") or "",
        "fullname": nickname,
        "first_name": nickname,
    }


def login_with_kakao_access_token(access_token: str) -> KakaoMobileAuthResult:
    """카카오 액세스 토큰으로 Django 사용자를 조회·생성하고 DRF Token을 발급한다."""
    raw = (access_token or "").strip()
    if not raw:
        raise KakaoMobileAuthError("access_token_required")

    payload = _fetch_kakao_profile(raw)
    uid = payload.get("id")
    if uid is None:
        raise KakaoMobileAuthError("kakao_uid_missing")

    username = f"kakao_{uid}"
    existed = User.objects.filter(username=username, is_active=True).exists()
    details = _details_from_kakao_response(payload)
    result = create_or_update_kakao_user(
        strategy=None,
        backend=_KakaoBackendStub(),
        uid=str(uid),
        details=details,
        user=None,
        response=payload,
    )
    user = result.get("user")
    if user is None or not user.is_active:
        raise KakaoMobileAuthError("user_inactive")

    from rest_framework.authtoken.models import Token

    token, _ = Token.objects.get_or_create(user=user)
    return KakaoMobileAuthResult(user=user, token_key=token.key, created=not existed)
