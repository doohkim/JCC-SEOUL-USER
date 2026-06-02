"""수련회 숙소·호실 모델."""

from __future__ import annotations

from django.db import models

from .event import RetreatEvent


class Lodging(models.Model):
    """행사별 숙소(건물/장소)."""

    event = models.ForeignKey(
        RetreatEvent,
        on_delete=models.CASCADE,
        related_name="lodgings",
        verbose_name="행사",
    )
    region = models.ForeignKey(
        "users.Region",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retreat_lodgings",
        verbose_name="지역",
        help_text="비워두면 전 지역 공용 숙소로 처리됩니다.",
    )
    name = models.CharField("숙소명", max_length=80)
    address = models.CharField("주소", max_length=200, blank=True, default="")
    memo = models.CharField("메모", max_length=200, blank=True, default="")
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "수련회 숙소"
        verbose_name_plural = "수련회 숙소"
        ordering = ["event", "sort_order", "name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "name"],
                name="uniq_retreat_lodging_event_name",
            )
        ]

    def __str__(self) -> str:
        return f"{self.event.name} · {self.name}"


class LodgingRoom(models.Model):
    """숙소 내 호실."""

    class Gender(models.TextChoices):
        MALE = "male", "남성"
        FEMALE = "female", "여성"
        MIXED = "mixed", "혼성"
        UNKNOWN = "", "미지정"

    lodging = models.ForeignKey(
        Lodging,
        on_delete=models.CASCADE,
        related_name="rooms",
        verbose_name="숙소",
    )
    region = models.ForeignKey(
        "users.Region",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retreat_lodging_rooms",
        verbose_name="지역",
        help_text="비워두면 어느 조에도 노출되지 않습니다 (미배정).",
    )
    division = models.ForeignKey(
        "users.Division",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retreat_lodging_rooms",
        verbose_name="부서",
        help_text="비워두면 어느 조에도 노출되지 않습니다 (미배정).",
    )
    number = models.CharField("호수", max_length=30)
    capacity = models.PositiveSmallIntegerField(
        "정원",
        default=0,
        help_text="0 = 정원 무제한",
    )
    recommended_gender = models.CharField(
        "권장 성별",
        max_length=10,
        choices=Gender.choices,
        blank=True,
        default="",
    )
    memo = models.CharField("메모", max_length=200, blank=True, default="")
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "수련회 호실"
        verbose_name_plural = "수련회 호실"
        ordering = ["lodging", "sort_order", "number", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["lodging", "number"],
                name="uniq_retreat_lodging_room_number",
            )
        ]

    def __str__(self) -> str:
        return f"{self.lodging.name} {self.number}"

    @property
    def label(self) -> str:
        return f"{self.lodging.name} {self.number}".strip()
