"""
외부 서버 연동 API.

모든 엔드포인트는 **연동 서비스 키** 필요:

- ``X-JCC-Integration-Key: <Admin에서 발급받은 키>``
- 또는 ``Authorization: Integration <키>``

DRF Token(``rest_framework.authtoken``)으로 앱·클라이언트가 저장한 사용자 토큰을 검증할 수 있습니다.
토큰 발급은 별도 엔드포인트를 두지 않고, Django Admin 또는 ``/api/v1/integration/debug/issue-token/``(DEBUG·staff만) 등으로 확장 가능.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.authentication import IntegrationServiceAuthentication
from users.permissions import IsIntegrationService
from users.services.integration_snapshot import (
    build_integration_user_body,
    user_permission_snapshot,
)

User = get_user_model()


class IntegrationBaseView(APIView):
    """연동 전용: 세션 인증 없이 서비스 키만."""

    authentication_classes = [IntegrationServiceAuthentication]
    permission_classes = [IsIntegrationService]

    def get_parser_classes(self):
        from rest_framework.parsers import JSONParser

        return [JSONParser]


class IntegrationVerifyTokenView(IntegrationBaseView):
    """
    POST ``/api/v1/integration/verify-token/``

    Body: ``{"token": "<DRF Token key>"}``

    Response: ``valid``, 유효 시 ``user`` (프로필 + 권한 스냅샷).
    """

    def post(self, request, *args, **kwargs):
        raw = (request.data.get("token") or request.data.get("key") or "").strip()
        if not raw:
            return Response(
                {"valid": False, "reason": "token_required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from rest_framework.authtoken.models import Token
        except Exception:
            return Response(
                {"valid": False, "reason": "token_auth_not_configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            t = Token.objects.select_related("user").get(key=raw)
        except Token.DoesNotExist:
            return Response({"valid": False, "reason": "invalid_token"})

        user = t.user
        if not user.is_active:
            return Response({"valid": False, "reason": "user_inactive"})

        return Response({"valid": True, "user": build_integration_user_body(user)})


class IntegrationUserDetailView(IntegrationBaseView):
    """
    GET ``/api/v1/integration/users/<user_id>/``

    활성 사용자 한 명의 프로필 + 권한 스냅샷 (토큰 없이 id로 조회 — 연동 서버 신뢰 전제).
    """

    def get(self, request, user_id: int, *args, **kwargs):
        try:
            user = User.objects.select_related("role_level", "profile").get(pk=user_id)
        except User.DoesNotExist:
            return Response({"detail": "user not found"}, status=status.HTTP_404_NOT_FOUND)

        if not user.is_active:
            return Response({"detail": "user inactive"}, status=status.HTTP_404_NOT_FOUND)

        return Response({"user": build_integration_user_body(user)})


class IntegrationPermissionCheckView(IntegrationBaseView):
    """
    POST ``/api/v1/integration/permissions/check/``

    Body::

        {
          "user_id": 1,
          "checks": ["member_registry", "team_roster_tab"]
        }

    ``checks`` 가 비어 있으면 전체 권한 스냅샷의 ``access`` 객체만 반환.
    """

    _KNOWN = frozenset(
        {
            "member_registry",
            "team_roster_tab",
            "attendance_roster",
            "attendance_manager",
            "platform_admin",
            "parking_manager",
            "account_management",
        }
    )

    def post(self, request, *args, **kwargs):
        uid = request.data.get("user_id")
        if uid is None:
            return Response({"detail": "user_id required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            uid = int(uid)
        except (TypeError, ValueError):
            return Response({"detail": "user_id invalid"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.select_related("role_level", "profile").get(pk=uid)
        except User.DoesNotExist:
            return Response({"detail": "user not found"}, status=status.HTTP_404_NOT_FOUND)

        if not user.is_active:
            return Response({"detail": "user inactive"}, status=status.HTTP_404_NOT_FOUND)

        snap = user_permission_snapshot(user)
        access = snap.get("access") or {}
        checks_in = request.data.get("checks")
        if not checks_in:
            return Response({"user_id": uid, "access": access})

        if not isinstance(checks_in, (list, tuple)):
            return Response({"detail": "checks must be a list"}, status=status.HTTP_400_BAD_REQUEST)

        unknown = [c for c in checks_in if c not in self._KNOWN]
        if unknown:
            return Response(
                {"detail": "unknown checks", "unknown": unknown, "allowed": sorted(self._KNOWN)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = {c: bool(access.get(c)) for c in checks_in}
        return Response({"user_id": uid, "results": results})


class IntegrationPingView(IntegrationBaseView):
    """GET ``/api/v1/integration/ping/`` — 서비스 키만 확인."""

    def get(self, request, *args, **kwargs):
        client = request.auth
        return Response(
            {
                "ok": True,
                "client": getattr(client, "name", None),
                "label": getattr(client, "label", None),
            }
        )


class IntegrationIssueTokenDebugView(IntegrationBaseView):
    """
    POST ``/api/v1/integration/debug/issue-token/`` (DEBUG 또는 ALLOW_INTEGRATION_DEBUG_TOKEN)

    Body: ``{"user_id": 1}`` — 해당 사용자용 DRF Token 생성/재발급.
    **운영에서는 비활성화** 권장.
    """

    def post(self, request, *args, **kwargs):
        allow = settings.DEBUG or getattr(settings, "ALLOW_INTEGRATION_DEBUG_TOKEN", False)
        if not allow:
            return Response({"detail": "disabled"}, status=status.HTTP_404_NOT_FOUND)

        uid = request.data.get("user_id")
        try:
            uid = int(uid)
        except (TypeError, ValueError):
            return Response({"detail": "user_id required"}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(pk=uid, is_active=True).first()
        if not user:
            return Response({"detail": "user not found"}, status=status.HTTP_404_NOT_FOUND)

        from rest_framework.authtoken.models import Token

        Token.objects.filter(user=user).delete()
        t = Token.objects.create(user=user)
        return Response({"user_id": user.id, "username": user.username, "token": t.key})
