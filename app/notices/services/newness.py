"""공지 NEW 배지 — 작성일(로컬 캘린더 당일) 기준."""

from __future__ import annotations

from datetime import datetime, time

from django.utils import timezone


def local_day_start(day=None) -> datetime:
    """로컬 타임존 기준 해당일 00:00."""
    if day is None:
        day = timezone.localdate()
    return timezone.make_aware(
        datetime.combine(day, time.min),
        timezone.get_current_timezone(),
    )


def is_created_today(created_at: datetime | None) -> bool:
    if not created_at:
        return False
    return timezone.localtime(created_at).date() == timezone.localdate()


def has_notices_created_today() -> bool:
    from notices.models import Notice

    return Notice.objects.filter(created_at__gte=local_day_start()).exists()
