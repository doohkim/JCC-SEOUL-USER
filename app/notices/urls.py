"""공지·타임테이블 URL."""

from django.urls import path

from notices.apis.categories import NoticeCategoryListAPIView
from notices.apis.notices import NoticeDetailAPIView, NoticeListAPIView
from notices.views import (
    NoticeCreateView,
    NoticeDeleteView,
    NoticeDetailView,
    NoticeListView,
    NoticeUpdateView,
    TimetableView,
    notice_image_upload,
)

urlpatterns = [
    path("api/v1/notices/categories/", NoticeCategoryListAPIView.as_view(), name="notice_category_list_api"),
    path("api/v1/notices/", NoticeListAPIView.as_view(), name="notice_list_api"),
    path("api/v1/notices/<int:notice_id>/", NoticeDetailAPIView.as_view(), name="notice_detail_api"),
    path("notices/", NoticeListView.as_view(), name="notice_list"),
    path("notices/upload-image/", notice_image_upload, name="notice_image_upload"),
    path("notices/new/", NoticeCreateView.as_view(), name="notice_create"),
    path("notices/<int:pk>/", NoticeDetailView.as_view(), name="notice_detail"),
    path("notices/<int:pk>/edit/", NoticeUpdateView.as_view(), name="notice_edit"),
    path("notices/<int:pk>/delete/", NoticeDeleteView.as_view(), name="notice_delete"),
    path("timetable/", TimetableView.as_view(), name="timetable"),
]
