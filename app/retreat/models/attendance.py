"""수련회 출석 기록."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from .enrollment import RetreatSessionAttendee


class RetreatAttendance(models.Model):
    """출석부 조원 스냅샷 단위 출석 결과."""

    class Status(models.TextChoices):
        PRESENT = "present", "참석"
        ABSENT = "absent", "결석"

    enrollment = models.OneToOneField(
        RetreatSessionAttendee,
        on_delete=models.CASCADE,
        related_name="attendance",
        verbose_name="출석부 조원",
    )
    status = models.CharField(
        "상태",
        max_length=10,
        choices=Status.choices,
        default=Status.PRESENT,
    )
    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retreat_attendance_checks",
        verbose_name="기록자",
    )
    checked_at = models.DateTimeField("기록 일시", auto_now=True)
    note = models.CharField("메모", max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "수련회 출석"
        verbose_name_plural = "수련회 출석"
        ordering = ["enrollment__session", "enrollment"]
        indexes = [
            models.Index(
                fields=["status"],
                name="idx_retreat_att_status",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.enrollment.name} · {self.enrollment.session.name} · "
            f"{self.get_status_display()}"
        )
