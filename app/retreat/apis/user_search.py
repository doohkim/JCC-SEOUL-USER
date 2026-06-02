"""수련회 운영진·회장단 등록을 위한 사용자 검색.

자동완성 용도. ``can_access_retreat_tab`` 통과한 사용자만 호출 가능하고,
username / display_name 부분 일치로 활성 사용자를 최대 N건 반환한다.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import can_access_retreat_tab

User = get_user_model()

_DEFAULT_LIMIT = 10
_MAX_LIMIT = 30


class RetreatUserSearchView(APIView):
    """GET /api/v1/retreat/users/search/?q=...&limit=20"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not can_access_retreat_tab(request.user):
            raise PermissionDenied("수련회 화면 접근 권한이 없습니다.")

        q = (request.query_params.get("q") or "").strip()
        try:
            limit = int(request.query_params.get("limit") or _DEFAULT_LIMIT)
        except (TypeError, ValueError):
            limit = _DEFAULT_LIMIT
        limit = max(1, min(limit, _MAX_LIMIT))

        qs = User.objects.filter(is_active=True).select_related("profile")
        if q:
            qs = qs.filter(
                Q(username__icontains=q) | Q(profile__display_name__icontains=q)
            )
        qs = qs.order_by("username")[:limit]

        results = []
        for u in qs:
            display = getattr(getattr(u, "profile", None), "display_name", "") or ""
            name = display or u.username
            results.append(
                {
                    "id": u.id,
                    "username": u.username,
                    "display_name": display,
                    "name": name,
                    # 옛 클라이언트 호환용. 새 UI는 name만 본다.
                    "label": name,
                }
            )
        return Response(results)
