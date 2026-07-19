"""수련회 모델 신호."""

from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from retreat.models import RetreatSession
from retreat.services.enrollment import snapshot_session_enrollments


@receiver(post_save, sender=RetreatSession)
def snapshot_new_retreat_session(
    sender, instance: RetreatSession, created: bool, raw: bool, **kwargs
):
    if raw or not created:
        return
    snapshot_session_enrollments(instance, actor=instance.created_by)
