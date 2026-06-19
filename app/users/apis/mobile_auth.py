"""모바일 앱 인증 API (카카오 토큰 → DRF Token)."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.mixins import ensure_user_profile, is_onboarding_complete
from users.permissions import can_access_notices_tab
from users.services.integration_snapshot import build_integration_user_body
from users.services.kakao_mobile_auth import KakaoMobileAuthError, login_with_kakao_access_token


class KakaoMobileLoginView(APIView):
    """
    POST ``/api/v1/auth/kakao/``

    Body: ``{"access_token": "<카카오 OAuth access token>"}``

    iOS Kakao SDK 로그인 후 받은 access token을 서버에 전달하면
    Django 사용자를 생성·갱신하고 DRF Token을 발급한다.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        access_token = (request.data.get("access_token") or "").strip()
        if not access_token:
            return Response(
                {"detail": "access_token required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = login_with_kakao_access_token(access_token)
        except KakaoMobileAuthError as exc:
            code = exc.code
            if code == "access_token_required":
                return Response({"detail": "access_token required"}, status=status.HTTP_400_BAD_REQUEST)
            if code == "invalid_kakao_token":
                return Response({"detail": "invalid kakao token"}, status=status.HTTP_401_UNAUTHORIZED)
            return Response({"detail": exc.message or code}, status=status.HTTP_502_BAD_GATEWAY)

        user = result.user
        profile = ensure_user_profile(user)
        return Response(
            {
                "token": result.token_key,
                "created": result.created,
                "onboarding_complete": is_onboarding_complete(user, profile),
                "can_access_notices": can_access_notices_tab(user),
                "user": build_integration_user_body(user),
            },
            status=status.HTTP_200_OK,
        )


class MobileMeView(APIView):
    """GET ``/api/v1/auth/me/`` — 저장된 Token으로 현재 사용자 정보."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        profile = ensure_user_profile(user)
        return Response(
            {
                "onboarding_complete": is_onboarding_complete(user, profile),
                "can_access_notices": can_access_notices_tab(user),
                "user": build_integration_user_body(user),
            }
        )
