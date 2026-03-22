"""API v1 라우팅 (users 앱에서 include)."""

from django.urls import include, path

urlpatterns = [
    path("org/", include("registry.api.urls")),
    path("attendance/", include("attendance.api.urls")),
]
