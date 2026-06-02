"""지역·부서·팀·메타 선택지 API."""

from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from attendance.apis.common import division_for_attendance_request
from attendance.serializers import (
    AttendanceMetaSerializer,
    DivisionBriefSerializer,
    TeamBriefSerializer,
)
from attendance.services.attendance_summary import build_meta_choices_payload
from users.models import Team
from users.permissions import visible_divisions_for, visible_regions_for


class AttendanceRegionListView(APIView):
    """현재 사용자에게 노출 가능한 지역 목록."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = visible_regions_for(request.user)
        return Response(
            [{"code": r.code, "name": r.name} for r in qs]
        )


class AttendanceDivisionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        region_code = (request.query_params.get("region_code") or "").strip() or None
        qs = (
            visible_divisions_for(request.user, region=region_code)
            .select_related("region")
            .order_by("region__sort_order", "sort_order", "name")
        )
        return Response(DivisionBriefSerializer(qs, many=True).data)


class AttendanceTeamListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        div = division_for_attendance_request(request)
        teams = Team.objects.filter(division=div).order_by("sort_order", "name")
        return Response(TeamBriefSerializer(teams, many=True).data)


class AttendanceMetaChoicesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payload = build_meta_choices_payload()
        return Response(AttendanceMetaSerializer(instance=payload).data)
