"""DRF 인증 — 외부 연동 서비스 키."""

from __future__ import annotations

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from users.models import ExternalServiceClient


class IntegrationServiceAuthentication(BaseAuthentication):
    """
    헤더 중 하나:
    - ``X-JCC-Integration-Key: <평문 키>``
    - ``Authorization: Integration <평문 키>``

    성공 시 ``request.auth`` 에 :class:`ExternalServiceClient` 인스턴스.
    ``request.user`` 는 익명(연동 호출에는 사용자 로그인 없음).
    """

    keyword = "integration"

    def authenticate_header(self, request):
        # 없으면 DRF가 AuthenticationFailed를 403으로 강등함 — 연동 키는 401이 맞음.
        return "Integration"

    def authenticate(self, request):
        if not getattr(settings, "INTEGRATION_API_ENABLED", True):
            return None

        raw = request.META.get("HTTP_X_JCC_INTEGRATION_KEY")
        if not raw:
            raw = self._from_authorization(request)
        if not raw:
            return None

        client = ExternalServiceClient.objects.filter(key_prefix=raw[:16], is_active=True).first()
        if client is None or not client.check_key(raw):
            raise AuthenticationFailed("Invalid integration key.")

        client.touch_last_used()
        return (None, client)

    def _from_authorization(self, request) -> str | None:
        h = request.META.get("HTTP_AUTHORIZATION", "")
        if not h:
            return None
        parts = h.split()
        if len(parts) != 2:
            return None
        scheme, token = parts[0].lower(), parts[1]
        if scheme != self.keyword:
            return None
        return token
