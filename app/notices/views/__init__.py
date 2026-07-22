from .notices import (
    FaqCreateView,
    FaqDeleteView,
    FaqUpdateView,
    FaqView,
    NoticeCreateView,
    NoticeDeleteView,
    NoticeDetailView,
    NoticeListView,
    NoticeUpdateView,
    TimetableView,
)
from .uploads import notice_image_upload

__all__ = [
    "NoticeListView",
    "NoticeDetailView",
    "NoticeCreateView",
    "NoticeUpdateView",
    "NoticeDeleteView",
    "TimetableView",
    "FaqView",
    "FaqCreateView",
    "FaqUpdateView",
    "FaqDeleteView",
    "notice_image_upload",
]
