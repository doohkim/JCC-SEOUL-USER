"""운영진 참가 신청."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from .event import RetreatEvent
from .group import RetreatGroup, RetreatGroupMembership


class StaffApplicationTrack(models.TextChoices):
    COUNCIL = "council", "집회 운영진"
    GROUP_LEADERSHIP = "group_leadership", "조 운영진"


class RetreatStaffApplication(models.Model):
    """집회 운영진 참가 신청 (회장단 승인 후 멤버십 반영)."""

    class Status(models.TextChoices):
        PENDING = "pending", "검토 중"
        APPROVED = "approved", "승인"
        REJECTED = "rejected", "반려"

    event = models.ForeignKey(
        RetreatEvent,
        on_delete=models.CASCADE,
        related_name="staff_applications",
        verbose_name="집회",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="retreat_staff_applications",
        verbose_name="신청자",
    )
    region = models.ForeignKey(
        "users.Region",
        on_delete=models.PROTECT,
        related_name="retreat_staff_applications",
        verbose_name="지역",
    )
    division = models.ForeignKey(
        "users.Division",
        on_delete=models.PROTECT,
        related_name="retreat_staff_applications",
        verbose_name="부서",
    )
    application_track = models.CharField(
        "신청 유형",
        max_length=24,
        choices=StaffApplicationTrack.choices,
        blank=True,
        default="",
    )
    group = models.ForeignKey(
        RetreatGroup,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="staff_applications",
        verbose_name="조",
    )
    group_role = models.CharField(
        "조 역할",
        max_length=20,
        choices=RetreatGroupMembership.Role.choices,
        blank=True,
        default="",
    )
    status = models.CharField(
        "상태",
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    note = models.CharField("메모", max_length=200, blank=True, default="")
    rejection_reason = models.CharField(
        "반려 사유",
        max_length=500,
        blank=True,
        default="",
    )
    approved_council_role = models.CharField(
        "승인 council 역할",
        max_length=32,
        blank=True,
        default="",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retreat_staff_applications_reviewed",
        verbose_name="검토자",
    )
    reviewed_at = models.DateTimeField("검토 일시", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "운영진 참가 신청"
        verbose_name_plural = "운영진 참가 신청"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "user"],
                condition=models.Q(status__in=["pending", "approved"]),
                name="uniq_retreat_staff_app_event_user_active",
            )
        ]

    def __str__(self) -> str:
        return f"{self.event.name} · {self.user_id} ({self.get_status_display()})"
