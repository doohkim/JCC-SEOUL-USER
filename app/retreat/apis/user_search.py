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
_ALL_MAX_LIMIT = 1000


class RetreatUserSearchView(APIView):
    """GET /api/v1/retreat/users/search/?q=...&division=..&region=..&limit=20

    ``division``(또는 ``region``)을 주면 해당 소속 계정만 반환한다. ``q`` 가
    비어 있어도 부서·지역 필터가 있으면 그 소속 전체 목록을 돌려준다.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not can_access_retreat_tab(request.user):
            raise PermissionDenied("수련회 화면 접근 권한이 없습니다.")

        q = (request.query_params.get("q") or "").strip()
        division_id = self._as_int(request.query_params.get("division"))
        region_id = self._as_int(request.query_params.get("region"))
        signup_source = (request.query_params.get("signup_source") or "").strip()
        all_users = (request.query_params.get("all") or "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        max_limit = _ALL_MAX_LIMIT if all_users else _MAX_LIMIT
        try:
            limit = int(request.query_params.get("limit") or _DEFAULT_LIMIT)
        except (TypeError, ValueError):
            limit = _DEFAULT_LIMIT
        limit = max(1, min(limit, max_limit))

        qs = User.objects.filter(is_active=True).select_related("profile")
        valid_sources = {c[0] for c in User.SignupSource.choices}
        if signup_source in valid_sources:
            qs = qs.filter(signup_source=signup_source)
        if division_id:
            qs = qs.filter(division_teams__division_id=division_id)
        elif region_id:
            qs = qs.filter(division_teams__division__region_id=region_id)
        if q:
            qs = qs.filter(
                Q(username__icontains=q) | Q(profile__display_name__icontains=q)
            )
        elif not (division_id or region_id or all_users):
            # 필터도 검색어도 없고 all 플래그도 없으면 빈 목록(전체 계정 노출 방지).
            return Response([])
        qs = qs.distinct().order_by("username")[:limit]

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

    @staticmethod
    def _as_int(value):
        try:
            return int(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None
