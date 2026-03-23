"""주간 집계(rollup) API."""

from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from attendance.apis.common import division_for_attendance_request
from attendance.serializers import (
    AttendanceWeekRollupSerializer,
    AttendanceWeekSummarySerializer,
)
from attendance.services.attendance_summary import build_week_summary_payload
from attendance.services.week_rollup import (
    distinct_week_sundays_for_division,
    parse_week_rollup_key,
    rollup_row_for_week,
)


class AttendanceWeekListView(APIView):
    """
    주차별 집계 목록 (저장 테이블 없음).

    Query: division_code (기본 youth), limit (기본 52)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        division = division_for_attendance_request(request)
        try:
            limit = int(request.query_params.get("limit") or 52)
        except ValueError:
            limit = 52
        limit = max(1, min(limit, 104))

        weeks = distinct_week_sundays_for_division(division)[:limit]
        rows = [rollup_row_for_week(division, ws) for ws in weeks]
        data = [AttendanceWeekRollupSerializer(instance=r).data for r in rows]
        return Response(data)


class AttendanceWeekSummaryView(APIView):
    """
    한 주(기준 주일) 집계.

    path week_sunday: YYYY-MM-DD (그 주 임의 날짜도 기준 일요일로 정규화)

    Query: division_code, worship_type = all|sunday|wednesday|saturday|midweek
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, week_sunday: str):
        division = division_for_attendance_request(request)
        ws = parse_week_rollup_key(week_sunday)
        wtype = (request.query_params.get("worship_type") or "all").lower()
        payload = build_week_summary_payload(division, ws, wtype)
        return Response(AttendanceWeekSummarySerializer(instance=payload).data)
