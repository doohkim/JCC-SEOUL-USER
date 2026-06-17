"""수련회 집회·세션(출석부)."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class RetreatEvent(models.Model):
    """수련회 집회. 예) '2026 여름 전국 수련회'."""

    name = models.CharField("집회명", max_length=120)
    start_date = models.DateField("시작일")
    end_date = models.DateField("종료일")
    is_active = models.BooleanField(
        "활성",
        default=True,
        help_text="비활성화 시 API 목록/관리 화면에서 숨김(데이터는 보존).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "수련회 집회"
        verbose_name_plural = "수련회 집회"
        ordering = ["-start_date", "-id"]

    def __str__(self) -> str:
        return f"{self.name} ({self.start_date:%Y-%m-%d}~{self.end_date:%Y-%m-%d})"


class RetreatSession(models.Model):
    """집회 내 출석부(시간대별 체크 단위)."""

    class Status(models.TextChoices):
        ACTIVE = "active", "진행중"
        CLOSED = "closed", "마감"

    event = models.ForeignKey(
        RetreatEvent,
        on_delete=models.CASCADE,
        related_name="sessions",
        verbose_name="집회",
    )
    name = models.CharField("출석부 제목", max_length=120)
    occurs_at = models.DateTimeField("진행 일시", null=True, blank=True)
    sequence = models.PositiveSmallIntegerField(
        "순서",
        default=0,
        help_text="occurs_at 미지정 시 정렬 기준.",
    )
    location = models.CharField("장소", max_length=200, blank=True, default="")
    status = models.CharField(
        "상태",
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    closed_at = models.DateTimeField("마감 일시", null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retreat_sessions_closed",
        verbose_name="마감자",
    )
    created_at = models.DateTimeField("생성 일시", auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retreat_sessions_created",
        verbose_name="생성자",
    )

    class Meta:
        verbose_name = "수련회 출석부"
        verbose_name_plural = "수련회 출석부"
        ordering = ["event", "sequence", "occurs_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "name"],
                name="uniq_retreat_session_event_name",
            )
        ]

    def __str__(self) -> str:
        return f"{self.event.name} · {self.name}"

    @property
    def is_closed(self) -> bool:
        return self.status == self.Status.CLOSED

    def mark_closed(self, user=None, *, save: bool = True) -> None:
        self.status = self.Status.CLOSED
        self.closed_at = timezone.now()
        if user is not None and getattr(user, "is_authenticated", False):
            self.closed_by = user
        if save:
            self.save(update_fields=["status", "closed_at", "closed_by"])

    def mark_reopened(self, *, save: bool = True) -> None:
        self.status = self.Status.ACTIVE
        self.closed_at = None
        self.closed_by = None
        if save:
            self.save(update_fields=["status", "closed_at", "closed_by"])
