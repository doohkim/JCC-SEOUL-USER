"""수련회 픽업(입회/출회) 정보 — 계정·조원 연동 없는 단순 수집."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from .event import RetreatEvent


class RetreatPickup(models.Model):
    """집회별 입회/출회 픽업 정보."""

    class Direction(models.TextChoices):
        ARRIVAL = "arrival", "입회"
        DEPARTURE = "departure", "출회"

    event = models.ForeignKey(
        RetreatEvent,
        on_delete=models.CASCADE,
        related_name="pickups",
        verbose_name="집회",
    )
    direction = models.CharField(
        "구분",
        max_length=16,
        choices=Direction.choices,
        db_index=True,
    )
    number = models.PositiveIntegerField("번호")
    group = models.ForeignKey(
        "retreat.RetreatGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pickups",
        verbose_name="조",
    )
    name = models.CharField("이름", max_length=60)
    region = models.ForeignKey(
        "users.Region",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retreat_pickups",
        verbose_name="지역",
    )
    division = models.ForeignKey(
        "users.Division",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retreat_pickups",
        verbose_name="부서",
    )
    train_time = models.DateTimeField("열차 시각")
    boarding_place = models.CharField("탑승장소", max_length=120)
    contact = models.CharField("연락처", max_length=30)
    note = models.CharField("기타 참고사항", max_length=200, blank=True, default="")
    applicant_name = models.CharField(
        "신청자",
        max_length=60,
        blank=True,
        default="",
        help_text="등록 시점의 신청자 이름 스냅샷",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retreat_pickups_created",
        verbose_name="신청자 계정",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "수련회 픽업"
        verbose_name_plural = "수련회 픽업"
        ordering = ["event", "direction", "number", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "direction", "number"],
                name="uniq_retreat_pickup_event_direction_number",
            )
        ]

    def __str__(self) -> str:
        return f"{self.event.name} · {self.get_direction_display()} #{self.number} {self.name}"


class RetreatPickupLocation(models.Model):
    """집회 공통 탑승장소 목록 — 지역·부서 구분 없이 픽업 등록 시 드롭다운 선택용."""

    event = models.ForeignKey(
        RetreatEvent,
        on_delete=models.CASCADE,
        related_name="pickup_locations",
        verbose_name="집회",
    )
    name = models.CharField("탑승장소", max_length=120)
    sort_order = models.PositiveIntegerField("정렬", default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retreat_pickup_locations_created",
        verbose_name="등록자",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "수련회 탑승장소"
        verbose_name_plural = "수련회 탑승장소"
        ordering = ["sort_order", "name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "name"],
                name="uniq_retreat_pickup_location_event_name",
            )
        ]

    def __str__(self) -> str:
        return f"{self.event.name} · {self.name}"
