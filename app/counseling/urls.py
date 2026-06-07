"""상담 앱 URL (템플릿 + api/v1/counseling/...)."""

from django.urls import path

from counseling.apis.counseling import (
    PastorDayOverrideDetailApiView,
    PastorDayOverrideListApiView,
    PastorListApiView,
    PastorManageSlotsApiView,
    PastorSettingsApiView,
    PastorSlotsApiView,
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
    path("api/v1/counseling/pastors/", PastorListApiView.as_view(), name="api_counseling_pastors"),
    path(
        "api/v1/counseling/pastors/<int:pk>/slots/",
        PastorSlotsApiView.as_view(),
        name="api_counseling_pastor_slots",
    ),
    path(
        "api/v1/counseling/pastor/slots/",
        PastorManageSlotsApiView.as_view(),
        name="api_counseling_pastor_manage_slots",
    ),
    path(
        "api/v1/counseling/pastor/settings/",
        PastorSettingsApiView.as_view(),
        name="api_counseling_pastor_settings",
    ),
    path(
        "api/v1/counseling/pastor/day-overrides/",
        PastorDayOverrideListApiView.as_view(),
        name="api_counseling_day_overrides",
    ),
    path(
        "api/v1/counseling/pastor/day-overrides/<str:date>/",
        PastorDayOverrideDetailApiView.as_view(),
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
