"""공지·타임테이블 URL."""

from django.urls import path

from notices.views import (
    NoticeCreateView,
    NoticeDeleteView,
    NoticeDetailView,
    NoticeListView,
    NoticeUpdateView,
    TimetableView,
)

urlpatterns = [
    path("notices/", NoticeListView.as_view(), name="notice_list"),
    path("notices/new/", NoticeCreateView.as_view(), name="notice_create"),
    path("notices/<int:pk>/", NoticeDetailView.as_view(), name="notice_detail"),
    path("notices/<int:pk>/edit/", NoticeUpdateView.as_view(), name="notice_edit"),
    path("notices/<int:pk>/delete/", NoticeDeleteView.as_view(), name="notice_delete"),
    path("timetable/", TimetableView.as_view(), name="timetable"),
]
