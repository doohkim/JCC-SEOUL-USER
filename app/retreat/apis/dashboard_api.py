"""대시보드·결과·변경 이력 API."""

from __future__ import annotations

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.models import RetreatEvent
from retreat.serializers import RetreatChangeLogSerializer
from retreat.services.dashboard import (
    build_event_results,
    build_group_attendance_board,
    build_realtime_dashboard,
    build_results_analytics,
)
from retreat.services.changelog_query import (
    CHANGELOG_PAGE_SIZE,
    changelog_queryset_for_event,
    parse_changelog_filters,
    parse_page,
    parse_page_size,
)
from users.permissions import (
    can_access_retreat_tab,
    can_view_retreat_all,
    is_retreat_staff,
    visible_retreat_sessions_for,
)


def _staff_view(user, event: RetreatEvent) -> bool:
    return can_view_retreat_all(user, event)


class RetreatEventDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        if not can_access_retreat_tab(request.user):
            raise PermissionDenied
        staff = _staff_view(request.user, event)
        return Response(build_realtime_dashboard(event, request.user, staff_view=staff))


class RetreatEventGroupBoardView(APIView):
    """조별 조원 명단 + 실시간 입·퇴실 상태 보드."""

    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        if not can_access_retreat_tab(request.user):
            raise PermissionDenied
        staff = _staff_view(request.user, event)
        return Response(
            build_group_attendance_board(event, request.user, staff_view=staff)
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
            build_event_results(event, request.user, session=session, staff_view=staff)
        )


class RetreatEventResultsAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        if not can_access_retreat_tab(request.user):
            raise PermissionDenied
        staff = _staff_view(request.user, event)
        return Response(build_results_analytics(event, request.user, staff_view=staff))


class RetreatEventChangelogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        if not is_retreat_staff(request.user, event):
            raise PermissionDenied("변경 이력 조회 권한이 없습니다.")
        filters = parse_changelog_filters(request.query_params)
        qs = changelog_queryset_for_event(event, **filters)
        page_size = parse_page_size(request.query_params, default=CHANGELOG_PAGE_SIZE)
        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(parse_page(request.query_params))
        return Response(
            {
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": page_size,
                "results": RetreatChangeLogSerializer(
                    page_obj.object_list, many=True
                ).data,
            }
        )
