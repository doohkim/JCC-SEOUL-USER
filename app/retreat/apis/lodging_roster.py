"""수련회 전체 명단 서버 페이지네이션 API."""

from __future__ import annotations

from dataclasses import asdict

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.models import RetreatEvent
from retreat.services.lodging import room_assignment_options_for_groups
from retreat.services.lodging_roster import (
    LODGING_ROSTER_PAGE_SIZE,
    build_lodging_roster_context,
    build_lodging_roster_page_context,
    filter_and_sort_lodging_roster,
    lodging_roster_summary,
)
from retreat.services.staff_capabilities import effective_capabilities
from users.permissions import can_view_retreat_group_roster


class RetreatEventLodgingRosterPageView(APIView):
    """권한 범위 내 전체 명단을 필터링해 현재 20명만 반환한다."""

    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        if not can_view_retreat_group_roster(request.user, event):
            raise PermissionDenied("이 집회의 전체 명단을 볼 권한이 없습니다.")

        context = build_lodging_roster_page_context(
            event,
            request.user,
            page_number=request.query_params.get("page") or 1,
            params=request.query_params,
        )
        if context is None:
            context = build_lodging_roster_context(event, request.user)
            filtered = filter_and_sort_lodging_roster(
                context["roster_attendees"], request.query_params
            )
            paginator = Paginator(filtered, LODGING_ROSTER_PAGE_SIZE)
            page_obj = paginator.get_page(request.query_params.get("page") or 1)
            attendees = list(page_obj.object_list)
            summary = lodging_roster_summary(filtered)
        else:
            page_obj = context["roster_page"]
            paginator = page_obj.paginator
            attendees = context["roster_attendees"]
            summary = context["roster_summary"]
        can_edit = bool(
            request.user.is_superuser
            or effective_capabilities(request.user, event).edit_attendee_profile
        )
        groups_by_id = {}
        for attendee in attendees:
            attendee.can_edit_roster = can_edit
            groups_by_id.setdefault(attendee.group_id, attendee.group)

        rows_html = render_to_string(
            "retreat/_lodging_roster_rows.html",
            {
                "event": event,
                "roster_attendees": attendees,
                "roster_any_can_edit": bool(attendees) and can_edit,
                "row_offset": page_obj.start_index() - 1 if paginator.count else 0,
            },
            request=request,
        )
        return Response(
            {
                "rows_html": rows_html,
                "page": page_obj.number,
                "page_size": LODGING_ROSTER_PAGE_SIZE,
                "total": paginator.count,
                "total_pages": paginator.num_pages,
                "start": page_obj.start_index() if paginator.count else 0,
                "end": page_obj.end_index() if paginator.count else 0,
                "summary": asdict(summary),
                "group_rooms": (
                    room_assignment_options_for_groups(event, groups_by_id.values())
                    if can_edit and groups_by_id
                    else {}
                ),
            }
        )
