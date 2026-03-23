"""주일·수토 출석 행 목록 API."""

from __future__ import annotations

from django.db.models import Case, IntegerField, Q, Value, When
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from attendance.apis.common import StandardPagination, division_for_attendance_request
from attendance.choices import MidweekAttendanceStatus, MidweekServiceType, WorshipVenue
from attendance.serializers import MidweekRecordRowSerializer, SundayAttendanceLineRowSerializer
from attendance.services.week_rollup import (
    midweek_records_for_week,
    parse_week_rollup_key,
    sunday_lines_for_week,
)
from users.models import Team


class AttendanceSundayLineListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get(self, request, week_sunday: str):
        division = division_for_attendance_request(request)
        ws = parse_week_rollup_key(week_sunday)
        qs = (
            sunday_lines_for_week(division, ws)
            .select_related("member", "team")
            .annotate(
                venue_order=Case(
                    When(venue=WorshipVenue.SEOUL, then=Value(1)),
                    When(venue=WorshipVenue.INCHEON, then=Value(2)),
                    When(venue=WorshipVenue.ONLINE, then=Value(3)),
                    When(venue=WorshipVenue.BRANCH, then=Value(4)),
                    default=Value(5),
                    output_field=IntegerField(),
                )
            )
            .order_by("venue_order", "session_part", "member__name")
        )

        venue = request.query_params.get("venue")
        if venue:
            qs = qs.filter(venue=venue)

        part = request.query_params.get("session_part")
        if part is not None and part != "":
            try:
                qs = qs.filter(session_part=int(part))
            except ValueError:
                pass

        team_id = request.query_params.get("team_id")
        if team_id:
            team = Team.objects.filter(pk=team_id, division=division).first()
            if team:
                qs = qs.filter(
                    Q(team_name_snapshot=team.name) | Q(team_id=team.id)
                )
            else:
                qs = qs.none()

        q = (request.query_params.get("search") or "").strip()
        if q:
            qs = qs.filter(
                Q(member__name__icontains=q) | Q(member__name_alias__icontains=q)
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        ser = SundayAttendanceLineRowSerializer(page, many=True)
        resp = paginator.get_paginated_response(ser.data)
        resp.data["stats"] = {
            "on_site": qs.filter(venue__in=[WorshipVenue.SEOUL, WorshipVenue.INCHEON]).count(),
            "online": qs.filter(venue=WorshipVenue.ONLINE).count(),
            "branch": qs.filter(venue=WorshipVenue.BRANCH).count(),
            "absent": 0,
        }
        return resp


class AttendanceMidweekRecordListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get(self, request, week_sunday: str):
        division = division_for_attendance_request(request)
        ws = parse_week_rollup_key(week_sunday)
        qs = (
            midweek_records_for_week(division, ws)
            .select_related("member", "team")
            .annotate(
                status_order=Case(
                    When(status=MidweekAttendanceStatus.PRESENT, then=Value(1)),
                    When(status=MidweekAttendanceStatus.ONLINE, then=Value(2)),
                    When(status=MidweekAttendanceStatus.ABSENT, then=Value(3)),
                    default=Value(4),  # 미입력(status is null)
                    output_field=IntegerField(),
                )
            )
            .order_by("service_date", "service_type", "status_order", "member__name")
        )

        st = request.query_params.get("service_type")
        if st in (MidweekServiceType.WEDNESDAY, MidweekServiceType.SATURDAY):
            qs = qs.filter(service_type=st)

        status_f = request.query_params.get("status")
        if status_f in dict(MidweekAttendanceStatus.choices):
            qs = qs.filter(status=status_f)
        elif status_f in ("empty", "null"):
            qs = qs.filter(status__isnull=True)

        team_id = request.query_params.get("team_id")
        if team_id:
            team = Team.objects.filter(pk=team_id, division=division).first()
            if team:
                qs = qs.filter(
                    Q(team_name_snapshot=team.name) | Q(team_id=team.id)
                )
            else:
                qs = qs.none()

        q = (request.query_params.get("search") or "").strip()
        if q:
            qs = qs.filter(
                Q(member__name__icontains=q) | Q(member__name_alias__icontains=q)
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        ser = MidweekRecordRowSerializer(page, many=True)
        resp = paginator.get_paginated_response(ser.data)
        resp.data["stats"] = {
            "on_site": qs.filter(status=MidweekAttendanceStatus.PRESENT).count(),
            "online": qs.filter(status=MidweekAttendanceStatus.ONLINE).count(),
            "branch": 0,
            "absent": qs.filter(
                Q(status=MidweekAttendanceStatus.ABSENT) | Q(status__isnull=True)
            ).count(),
        }
        return resp
