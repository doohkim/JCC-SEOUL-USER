"""대시보드·결과·변경 이력 API."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.models import RetreatChangeLog, RetreatEvent
from retreat.serializers import RetreatChangeLogSerializer
from retreat.services.dashboard import (
    build_event_results,
    build_realtime_dashboard,
    build_results_analytics,
)
from users.permissions import (
    can_access_retreat_tab,
    is_retreat_staff,
    visible_retreat_sessions_for,
)


def _staff_view(user, event: RetreatEvent) -> bool:
    return bool(user.is_superuser or is_retreat_staff(user, event))


class RetreatEventDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        if not can_access_retreat_tab(request.user):
            raise PermissionDenied
        staff = _staff_view(request.user, event)
        return Response(
            build_realtime_dashboard(event, request.user, staff_view=staff)
        )


class RetreatEventResultsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        if not can_access_retreat_tab(request.user):
            raise PermissionDenied
        session = None
        session_id = request.query_params.get("session_id")
        if session_id:
            session = get_object_or_404(
                visible_retreat_sessions_for(request.user, event),
                pk=session_id,
            )
        staff = _staff_view(request.user, event)
        return Response(
            build_event_results(
                event, request.user, session=session, staff_view=staff
            )
        )


class RetreatEventResultsAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        if not can_access_retreat_tab(request.user):
            raise PermissionDenied
        staff = _staff_view(request.user, event)
        return Response(
            build_results_analytics(event, request.user, staff_view=staff)
        )


class RetreatEventChangelogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        if not (request.user.is_superuser or is_retreat_staff(request.user, event)):
            raise PermissionDenied("변경 이력 조회 권한이 없습니다.")
        limit = min(int(request.query_params.get("limit", 100)), 500)
        qs = (
            RetreatChangeLog.objects.filter(event=event)
            .select_related("changed_by")
            .order_by("-changed_at", "-id")[:limit]
        )
        return Response(RetreatChangeLogSerializer(qs, many=True).data)
