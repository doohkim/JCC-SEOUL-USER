from .notices import (
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
    "notice_image_upload",
]
