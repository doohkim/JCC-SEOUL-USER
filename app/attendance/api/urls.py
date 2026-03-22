from django.urls import path

from attendance.api.views import (
    AttendanceDivisionListView,
    AttendanceMetaChoicesView,
    AttendanceMidweekRecordListView,
    AttendanceSundayLineListView,
    AttendanceTeamListView,
    AttendanceWeekListView,
    AttendanceWeekSummaryView,
)

urlpatterns = [
    path("meta/", AttendanceMetaChoicesView.as_view(), name="api_attendance_meta"),
    path(
        "divisions/",
        AttendanceDivisionListView.as_view(),
        name="api_attendance_divisions",
    ),
    path("teams/", AttendanceTeamListView.as_view(), name="api_attendance_teams"),
    path("weeks/", AttendanceWeekListView.as_view(), name="api_attendance_weeks"),
    path(
        "weeks/<int:pk>/summary/",
        AttendanceWeekSummaryView.as_view(),
        name="api_attendance_week_summary",
    ),
    path(
        "weeks/<int:pk>/sunday/",
        AttendanceSundayLineListView.as_view(),
        name="api_attendance_week_sunday",
    ),
    path(
        "weeks/<int:pk>/midweek/",
        AttendanceMidweekRecordListView.as_view(),
        name="api_attendance_week_midweek",
    ),
]
