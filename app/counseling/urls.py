"""상담 앱 URL (템플릿 + api/v1/counseling/...)."""

from django.urls import path

from counseling.apis.counseling import (
    CounselorDayOverrideDetailApiView,
    CounselorDayOverrideListApiView,
    CounselorListApiView,
    CounselorManageSlotsApiView,
    CounselorSettingsApiView,
    CounselorSlotsApiView,
    CounselingRequestAcceptApiView,
    CounselingRequestDetailApiView,
    CounselingRequestListCreateApiView,
    CounselingRequestRejectApiView,
)
from counseling.views import CounselingHomeView, CounselingRequestDetailView

urlpatterns = [
    path("counseling/", CounselingHomeView.as_view(), name="counseling_home"),
    path(
        "counseling/requests/<uuid:public_id>/",
        CounselingRequestDetailView.as_view(),
        name="counseling_request_detail",
    ),
    path("api/v1/counseling/counselors/", CounselorListApiView.as_view(), name="api_counseling_counselors"),
    path(
        "api/v1/counseling/counselors/<int:pk>/slots/",
        CounselorSlotsApiView.as_view(),
        name="api_counseling_counselor_slots",
    ),
    path(
        "api/v1/counseling/counselor/slots/",
        CounselorManageSlotsApiView.as_view(),
        name="api_counseling_counselor_manage_slots",
    ),
    path(
        "api/v1/counseling/counselor/settings/",
        CounselorSettingsApiView.as_view(),
        name="api_counseling_counselor_settings",
    ),
    path(
        "api/v1/counseling/counselor/day-overrides/",
        CounselorDayOverrideListApiView.as_view(),
        name="api_counseling_day_overrides",
    ),
    path(
        "api/v1/counseling/counselor/day-overrides/<str:date>/",
        CounselorDayOverrideDetailApiView.as_view(),
        name="api_counseling_day_override_detail",
    ),
    path(
        "api/v1/counseling/requests/",
        CounselingRequestListCreateApiView.as_view(),
        name="api_counseling_requests",
    ),
    path(
        "api/v1/counseling/requests/<uuid:public_id>/",
        CounselingRequestDetailApiView.as_view(),
        name="api_counseling_request_detail",
    ),
    path(
        "api/v1/counseling/requests/<uuid:public_id>/accept/",
        CounselingRequestAcceptApiView.as_view(),
        name="api_counseling_request_accept",
    ),
    path(
        "api/v1/counseling/requests/<uuid:public_id>/reject/",
        CounselingRequestRejectApiView.as_view(),
        name="api_counseling_request_reject",
    ),
]
