"""attendance 앱 URL (템플릿 대시보드 + 출석 DRF)."""

from django.urls import path
from django.views.generic import RedirectView

from attendance.apis import (
    AttendanceDivisionListView,
    AttendanceMetaChoicesView,
    AttendanceMidweekRosterView,
    AttendanceMidweekRecordListView,
    AttendanceSundayRosterView,
    AttendanceSundayLineListView,
    AttendanceTeamListView,
    AttendanceWeekListView,
    AttendanceWeekSummaryView,
    AttendanceTeamMidweekRosterView,
    AttendanceTeamSundayRosterView,
)
from attendance.views import (
    AttendanceDashboardView,
    AttendanceRosterEditView,
    AttendanceRosterListView,
    AttendanceTeamRosterCheckView,
    AttendanceTeamRosterMyPageView,
)

urlpatterns = [
    path(
        "attendance/",
        AttendanceDashboardView.as_view(),
        name="attendance_dashboard",
    ),
    path("attendance/roster/", AttendanceRosterListView.as_view(), name="attendance_roster_list"),
    path(
        "attendance/roster/edit/",
        AttendanceRosterEditView.as_view(),
        name="attendance_roster_edit",
    ),
    path(
        "api/v1/attendance/meta/",
        AttendanceMetaChoicesView.as_view(),
        name="api_attendance_meta",
    ),
    path(
        "api/v1/attendance/divisions/",
        AttendanceDivisionListView.as_view(),
        name="api_attendance_divisions",
    ),
    path(
        "api/v1/attendance/teams/",
        AttendanceTeamListView.as_view(),
        name="api_attendance_teams",
    ),
    path(
        "api/v1/attendance/weeks/<str:week_sunday>/summary/",
        AttendanceWeekSummaryView.as_view(),
        name="api_attendance_week_summary",
    ),
    path(
        "api/v1/attendance/weeks/<str:week_sunday>/sunday/",
        AttendanceSundayLineListView.as_view(),
        name="api_attendance_week_sunday",
    ),
    path(
        "api/v1/attendance/weeks/<str:week_sunday>/midweek/",
        AttendanceMidweekRecordListView.as_view(),
        name="api_attendance_week_midweek",
    ),
    path(
        "api/v1/attendance/weeks/<str:week_sunday>/roster/midweek/",
        AttendanceMidweekRosterView.as_view(),
        name="api_attendance_week_midweek_roster",
    ),
    path(
        "api/v1/attendance/weeks/<str:week_sunday>/roster/sunday/",
        AttendanceSundayRosterView.as_view(),
        name="api_attendance_week_sunday_roster",
    ),
    # 팀장(본인 팀만) 전용 출석 체크 API
    path(
        "api/v1/attendance/team/weeks/<str:week_sunday>/roster/sunday/",
        AttendanceTeamSundayRosterView.as_view(),
        name="api_attendance_team_sunday_roster",
    ),
    path(
        "api/v1/attendance/team/weeks/<str:week_sunday>/roster/midweek/",
        AttendanceTeamMidweekRosterView.as_view(),
        name="api_attendance_team_midweek_roster",
    ),
    path(
        "api/v1/attendance/weeks/",
        AttendanceWeekListView.as_view(),
        name="api_attendance_weeks",
    ),
    # 팀장 전용 탭 출석부 페이지
    path(
        "attendance/team/roster/",
        AttendanceTeamRosterCheckView.as_view(),
        name="attendance_team_roster_check",
    ),
    path(
        "attendance/team/roster/my/",
        AttendanceTeamRosterMyPageView.as_view(),
        name="attendance_team_roster_mypage",
    ),
    # 브라우저에서 /api/v1/attendance/ 만 치면 404 나므로 출석 UI로 보냄
    path(
        "api/v1/attendance/",
        RedirectView.as_view(url="/attendance/", permanent=False),
        name="api_attendance_root_redirect",
    ),
]
