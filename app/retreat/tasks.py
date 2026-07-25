"""수련회 Celery 작업."""

from __future__ import annotations

import logging

from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)

_LOCK_KEY = "retreat:auto_transition_check_in:lock"
_LOCK_TTL_SECONDS = 55


@shared_task(
    name="retreat.tasks.auto_transition_check_in",
    expires=50,
    soft_time_limit=45,
    time_limit=50,
)
def auto_transition_check_in() -> dict:
    """매분 실행: 예상 입·퇴실 시각이 지난 조원을 입실/퇴실로 자동 전환한다."""
    from retreat.services.auto_check_in import apply_due_auto_transitions

    if not cache.add(_LOCK_KEY, "1", timeout=_LOCK_TTL_SECONDS):
        logger.info("auto_transition_check_in skipped: lock held")
        return {"skipped": True, "pending": 0, "checked_in": 0, "checked_out": 0}
    try:
        return apply_due_auto_transitions()
    finally:
        cache.delete(_LOCK_KEY)
