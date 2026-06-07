"""수련회 Celery 작업."""

from __future__ import annotations

from celery import shared_task


@shared_task(name="retreat.tasks.auto_transition_check_in")
def auto_transition_check_in() -> dict:
    """매분 실행: 예상 입·퇴실 시각이 지난 조원을 입실/퇴실로 자동 전환한다."""
    from retreat.services.auto_check_in import apply_due_auto_transitions

    return apply_due_auto_transitions()
