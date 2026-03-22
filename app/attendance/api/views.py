"""주간 출석(주차·주일·수토) 조회 API — 대시보드·차트용."""

from __future__ import annotations

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from attendance.choices import (
    MidweekAttendanceStatus,
    MidweekServiceType,
    WorshipVenue,
)
from attendance.models import (
    AttendanceWeek,
    MidweekAttendanceRecord,
    SundayAttendanceLine,
)
from users.models import Division, Team


def _venue_label(code: str) -> str:
    return dict(WorshipVenue.choices).get(code, code)


def _midweek_status_label(code: str) -> str:
    return dict(MidweekAttendanceStatus.choices).get(code, code or "(미입력)")


def _service_label(code: str) -> str:
    return dict(MidweekServiceType.choices).get(code, code)


class StandardPagination(PageNumberPagination):
    page_size = 40
    page_size_query_param = "page_size"
    max_page_size = 200


class AttendanceDivisionListView(APIView):
    """부서 목록 (주차 필터용)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Division.objects.all().order_by("sort_order", "name")
        data = [
            {"id": d.pk, "code": d.code, "name": d.name} for d in qs
        ]
        return Response(data)


class AttendanceWeekListView(APIView):
    """
    주차 목록.

    Query: ``division_code`` (기본 youth), ``limit`` (최근 N주, 기본 52)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        code = request.query_params.get("division_code") or "youth"
        try:
            limit = int(request.query_params.get("limit") or 52)
        except ValueError:
            limit = 52
        limit = max(1, min(limit, 104))

        qs = (
            AttendanceWeek.objects.filter(division__code=code)
            .select_related("division")
            .annotate(
                _sunday=Count("sunday_lines", distinct=True),
                _midweek=Count("midweek_records", distinct=True),
            )
            .order_by("-week_sunday")[:limit]
        )
        data = [
            {
                "id": w.pk,
                "division_code": w.division.code,
                "division_name": w.division.name,
                "week_sunday": w.week_sunday.isoformat(),
                "sunday_line_count": w._sunday,
                "midweek_record_count": w._midweek,
                "note": w.note,
            }
            for w in qs
        ]
        return Response(data)


class AttendanceWeekSummaryView(APIView):
    """
    한 주차 집계 (차트용).

    Query: ``worship_type`` = ``all`` | ``sunday`` | ``wednesday`` | ``saturday`` | ``midweek``
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        week = get_object_or_404(
            AttendanceWeek.objects.select_related("division"), pk=pk
        )
        wtype = (request.query_params.get("worship_type") or "all").lower()

        out: dict = {
            "week": {
                "id": week.pk,
                "division_code": week.division.code,
                "division_name": week.division.name,
                "week_sunday": week.week_sunday.isoformat(),
            },
            "worship_type": wtype,
            "sunday": None,
            "midweek": None,
        }

        if wtype in ("all", "sunday"):
            sun_qs = SundayAttendanceLine.objects.filter(week=week)
            by_venue = dict(
                sun_qs.values("venue")
                .annotate(c=Count("id"))
                .values_list("venue", "c")
            )
            by_venue_display = {
                _venue_label(k): v for k, v in by_venue.items()
            }
            by_part_rows = (
                sun_qs.filter(venue__in=[WorshipVenue.SEOUL, WorshipVenue.INCHEON])
                .values("venue", "session_part")
                .annotate(c=Count("id"))
            )
            by_part = [
                {
                    "venue": r["venue"],
                    "venue_label": _venue_label(r["venue"]),
                    "session_part": r["session_part"],
                    "label": f'{_venue_label(r["venue"])} {r["session_part"]}부'
                    if r["session_part"]
                    else _venue_label(r["venue"]),
                    "count": r["c"],
                }
                for r in by_part_rows
            ]
            team_rows = (
                sun_qs.filter(team_id__isnull=False)
                .values("team_id", "team__name")
                .annotate(c=Count("id"))
                .order_by("-c")[:30]
            )
            by_team = [
                {
                    "team_id": r["team_id"],
                    "team_name": r["team__name"],
                    "count": r["c"],
                }
                for r in team_rows
            ]
            out["sunday"] = {
                "total_lines": sun_qs.count(),
                "by_venue": by_venue,
                "by_venue_display": by_venue_display,
                "by_venue_part": by_part,
                "by_team": by_team,
            }

        if wtype in ("all", "midweek", "wednesday", "saturday"):
            mw = MidweekAttendanceRecord.objects.filter(week=week)
            if wtype == "wednesday":
                mw = mw.filter(service_type=MidweekServiceType.WEDNESDAY)
            elif wtype == "saturday":
                mw = mw.filter(service_type=MidweekServiceType.SATURDAY)

            by_service = {}
            for st, st_label in MidweekServiceType.choices:
                if wtype in ("wednesday", "saturday") and st != wtype:
                    continue
                sub = mw.filter(service_type=st)
                agg = dict(
                    sub.exclude(status__isnull=True)
                    .values("status")
                    .annotate(c=Count("id"))
                    .values_list("status", "c")
                )
                by_status_labeled = {
                    _midweek_status_label(k): v for k, v in agg.items()
                }
                null_c = sub.filter(status__isnull=True).count()
                if null_c:
                    by_status_labeled["미입력"] = by_status_labeled.get("미입력", 0) + null_c
                by_service[st] = {
                    "label": st_label,
                    "total": sub.count(),
                    "by_status": by_status_labeled,
                }
            out["midweek"] = {
                "total_records": mw.count(),
                "by_service": by_service,
            }

        return Response(out)


class AttendanceSundayLineListView(APIView):
    """주일 출석 행 목록 + 필터 + 페이지."""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get(self, request, pk: int):
        week = get_object_or_404(AttendanceWeek.objects.select_related("division"), pk=pk)
        qs = (
            SundayAttendanceLine.objects.filter(week=week)
            .select_related("member", "team")
            .order_by("member__name", "venue", "session_part")
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
            qs = qs.filter(team_id=team_id)

        q = (request.query_params.get("search") or "").strip()
        if q:
            qs = qs.filter(
                Q(member__name__icontains=q)
                | Q(member__name_alias__icontains=q)
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        rows = [
            {
                "id": o.pk,
                "member_id": o.member_id,
                "member_name": o.member.name,
                "venue": o.venue,
                "venue_label": o.get_venue_display(),
                "session_part": o.session_part,
                "branch_label": o.branch_label,
                "team_id": o.team_id,
                "team_name": o.team.name if o.team_id else None,
            }
            for o in page
        ]
        return paginator.get_paginated_response(rows)


class AttendanceMidweekRecordListView(APIView):
    """수·토 출석 행 목록 + 필터 + 페이지."""

    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get(self, request, pk: int):
        week = get_object_or_404(AttendanceWeek.objects.select_related("division"), pk=pk)
        qs = (
            MidweekAttendanceRecord.objects.filter(week=week)
            .select_related("member")
            .order_by("service_type", "member__name")
        )

        st = request.query_params.get("service_type")
        if st in (MidweekServiceType.WEDNESDAY, MidweekServiceType.SATURDAY):
            qs = qs.filter(service_type=st)

        status_f = request.query_params.get("status")
        if status_f in dict(MidweekAttendanceStatus.choices):
            qs = qs.filter(status=status_f)
        elif status_f == "empty" or status_f == "null":
            qs = qs.filter(status__isnull=True)

        q = (request.query_params.get("search") or "").strip()
        if q:
            qs = qs.filter(
                Q(member__name__icontains=q)
                | Q(member__name_alias__icontains=q)
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        rows = [
            {
                "id": o.pk,
                "member_id": o.member_id,
                "member_name": o.member.name,
                "service_type": o.service_type,
                "service_label": o.get_service_type_display(),
                "status": o.status,
                "status_label": o.get_status_display() if o.status else None,
            }
            for o in page
        ]
        return paginator.get_paginated_response(rows)


class AttendanceTeamListView(APIView):
    """부서 소속 팀 목록 (주일 필터 드롭다운)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        code = request.query_params.get("division_code") or "youth"
        div = get_object_or_404(Division, code=code)
        teams = Team.objects.filter(division=div).order_by("sort_order", "name")
        data = [{"id": t.pk, "code": t.code, "name": t.name} for t in teams]
        return Response(data)


class AttendanceMetaChoicesView(APIView):
    """필터 UI용 상수."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "worship_types": [
                    {"value": "all", "label": "전체"},
                    {"value": "sunday", "label": "주일"},
                    {"value": "wednesday", "label": "수요일"},
                    {"value": "saturday", "label": "토요일"},
                    {"value": "midweek", "label": "수·토 전체"},
                ],
                "venues": [
                    {"value": c[0], "label": c[1]} for c in WorshipVenue.choices
                ],
                "midweek_service_types": [
                    {"value": c[0], "label": c[1]} for c in MidweekServiceType.choices
                ],
                "midweek_statuses": [
                    {"value": c[0], "label": c[1]} for c in MidweekAttendanceStatus.choices
                ],
            }
        )
