"""수련회 변경 이력."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from .event import RetreatEvent


class RetreatChangeLog(models.Model):
    """조원·출석부·출석·조 멤버십 등 변경 감사 로그."""

    class Action(models.TextChoices):
        CREATE = "create", "생성"
        UPDATE = "update", "수정"
        DELETE = "delete", "삭제"
        APPROVE = "approve", "승인"
        REJECT = "reject", "반려"

    class TargetType(models.TextChoices):
        SESSION = "session", "출석부"
        ATTENDEE = "attendee", "조원"
        ENROLLMENT = "enrollment", "출석부 조원"
        ATTENDANCE = "attendance", "출석"
        GROUP_MEMBERSHIP = "group_membership", "조 운영진"
        GROUP = "group", "조"
        PICKUP = "pickup", "픽업"
        PICKUP_LOCATION = "pickup_location", "탑승장소"
        TIMETABLE = "timetable", "타임테이블"
        STAFF_APPLICATION = "staff_application", "운영진 신청"

    event = models.ForeignKey(
        RetreatEvent,
        on_delete=models.CASCADE,
        related_name="change_logs",
        verbose_name="집회",
    )
    action = models.CharField("동작", max_length=10, choices=Action.choices)
    target_type = models.CharField(
        "대상 유형",
        max_length=30,
        choices=TargetType.choices,
    )
    target_id = models.PositiveIntegerField("대상 ID")
    payload_before = models.JSONField("변경 전", null=True, blank=True)
    payload_after = models.JSONField("변경 후", null=True, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retreat_change_logs",
        verbose_name="변경자",
    )
    changed_at = models.DateTimeField("변경 일시", auto_now_add=True)

    class Meta:
        verbose_name = "수련회 변경 이력"
        verbose_name_plural = "수련회 변경 이력"
        ordering = ["-changed_at", "-id"]
        indexes = [
            models.Index(
                fields=["event", "-changed_at"],
                name="idx_retreat_changelog_event_at",
            ),
            models.Index(
                fields=["target_type", "target_id"],
                name="idx_retreat_changelog_target",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_target_type_display()} #{self.target_id} · {self.get_action_display()}"
