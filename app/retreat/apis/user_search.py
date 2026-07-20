"""수련회 운영진·회장단 등록을 위한 사용자 검색.

자동완성 용도. ``can_access_retreat_tab`` 통과한 사용자만 호출 가능하고,
username / display_name 부분 일치로 활성 사용자를 최대 N건 반환한다.
"""

from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.models import RetreatAttendee
from retreat.services.staff_pool import (
    event_staff_eligible_division_ids,
    staff_pool_users_for_event,
)
from users.models import UserProfile
from users.permissions import can_access_retreat_tab
from users.services.user_display import user_account_link_label

User = get_user_model()


def _primary_affiliation_for_user(user):
    """주 소속 지역·부서 (UserDivisionTeam)."""
    row = (
        user.division_teams.order_by(
            "-is_primary", "sort_order", "division__sort_order", "id"
        )
        .select_related("division", "division__region")
        .first()
    )
    if row is None:
        return None, None, "", ""
    division = row.division
    region = division.region
    return (
        region.id if region else None,
        division.id,
        (region.name if region else "") or "",
        division.name or "",
    )


def _affiliations_for_user(user):
    """운영진 등록 모달용 다중 소속 목록."""
    rows = (
        user.division_teams.order_by(
            "-is_primary", "sort_order", "division__sort_order", "id"
        )
        .select_related("division", "division__region")
        .all()
    )
    values = [
        (
            row.division_id,
            row.division.region_id if row.division else None,
            row.division.name if row.division else "",
            (
                row.division.region.name
                if row.division and row.division.region_id
                else ""
            ),
        )
        for row in rows
        if row.division_id
    ]
    seen = set()
    results = []
    for division_id, region_id, division_name, region_name in values:
        if division_id in seen:
            continue
        seen.add(division_id)
        results.append(
            {
                "division_id": division_id,
                "region_id": region_id,
                "division_name": division_name or "",
                "region_name": region_name or "",
            }
        )
    return results


_DEFAULT_LIMIT = 10
_MAX_LIMIT = 30
_ALL_MAX_LIMIT = 1000


class RetreatUserSearchView(APIView):
    """GET /api/v1/retreat/users/search/?q=...&division=..&region=..&limit=20

    ``division``(또는 ``region``)을 주면 해당 소속 계정만 반환한다.
    ``division`` 은 ``?division=1&division=2`` 처럼 여러 번 넘기면
    대표·추가 지역·부서 소속을 합쳐 조회한다. ``q`` 가 비어 있어도
    부서·지역 필터가 있으면 그 소속 전체 목록을 돌려준다.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not can_access_retreat_tab(request.user):
            raise PermissionDenied("수련회 화면 접근 권한이 없습니다.")

        q = (request.query_params.get("q") or "").strip()
        division_ids = [
            d
            for raw in request.query_params.getlist("division")
            if (d := self._as_int(raw)) is not None
        ]
        region_id = self._as_int(request.query_params.get("region"))
        signup_source = (request.query_params.get("signup_source") or "").strip()
        event_id = self._as_int(request.query_params.get("event_id"))
        staff_pool = (request.query_params.get("staff_pool") or "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        staff_pool_kind = (request.query_params.get("staff_pool_kind") or "").strip()
        if staff_pool_kind not in {"council", "group"}:
            staff_pool_kind = "any"
        all_users = (request.query_params.get("all") or "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        max_limit = _ALL_MAX_LIMIT if all_users else _MAX_LIMIT
        if staff_pool and event_id:
            max_limit = max(max_limit, 100)
        try:
            limit = int(request.query_params.get("limit") or _DEFAULT_LIMIT)
        except (TypeError, ValueError):
            limit = _DEFAULT_LIMIT
        limit = max(1, min(limit, max_limit))

        qs = User.objects.filter(
            is_active=True, retired_at__isnull=True
        ).select_related("profile")
        if staff_pool and event_id:
            if not event_staff_eligible_division_ids(event_id):
                return Response([])
            qs = staff_pool_users_for_event(event_id, assign_kind=staff_pool_kind)
        elif event_id:
            event_user_ids = RetreatAttendee.objects.filter(
                group__event_id=event_id,
                user_id__isnull=False,
            ).values_list("user_id", flat=True)
            qs = qs.filter(id__in=event_user_ids)
        valid_sources = {c[0] for c in User.SignupSource.choices}
        if signup_source in valid_sources:
            qs = qs.filter(signup_source=signup_source)
        if division_ids:
            qs = qs.filter(division_teams__division_id__in=division_ids)
        elif region_id:
            qs = qs.filter(division_teams__division__region_id=region_id)
        if q:
            q_filter = (
                Q(username__icontains=q)
                | Q(profile__display_name__icontains=q)
                | Q(profile__real_name__icontains=q)
            )
            digits = re.sub(r"\D", "", q)
            if len(digits) >= 4:
                q_filter |= Q(profile__phone__icontains=digits[-4:])
            qs = qs.filter(q_filter)
        elif not (
            division_ids
            or region_id
            or event_id
            or all_users
            or (staff_pool and event_id)
        ):
            # 필터도 검색어도 없고 all 플래그도 없으면 빈 목록(전체 계정 노출 방지).
            return Response([])
        qs = qs.distinct().order_by("username")[:limit]

        results = []
        for u in qs:
            profile = getattr(u, "profile", None)
            display = getattr(profile, "display_name", "") or ""
            name = user_account_link_label(u)
            real_name = (getattr(profile, "real_name", "") or "").strip()
            phone = (getattr(profile, "phone", "") or "").strip()
            gender = (getattr(profile, "gender", "") or "").strip()
            if gender not in dict(RetreatAttendee.Gender.choices):
                gender = ""
            region_id, division_id, region_name, division_name = (
                _primary_affiliation_for_user(u)
            )
            affiliations = _affiliations_for_user(u)
            results.append(
                {
                    "id": u.id,
                    "username": u.username,
                    "display_name": display,
                    "name": name,
                    "real_name": real_name,
                    "phone": phone,
                    "gender": gender,
                    "region_id": region_id,
                    "division_id": division_id,
                    "region_name": region_name,
                    "division_name": division_name,
                    "is_pastoral": bool(
                        getattr(getattr(u, "role_level", None), "code", None)
                        in {"pastor", "evangelist"}
                    ),
                    "affiliations": affiliations,
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
