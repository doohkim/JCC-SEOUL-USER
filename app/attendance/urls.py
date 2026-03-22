from django.urls import path

from attendance.views import AttendanceDashboardView

urlpatterns = [
    path("", AttendanceDashboardView.as_view(), name="attendance_dashboard"),
]
