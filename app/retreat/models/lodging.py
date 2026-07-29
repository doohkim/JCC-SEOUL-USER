"""수련회 숙소·호실 모델."""

from __future__ import annotations

from django.db import models

from .event import RetreatEvent


class Lodging(models.Model):
    """집회별 숙소(건물/장소)."""

    event = models.ForeignKey(
        RetreatEvent,
        on_delete=models.CASCADE,
        related_name="lodgings",
        verbose_name="집회",
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
        "성별",
        max_length=10,
        choices=Gender.choices,
        blank=True,
        default="",
        help_text="남성 또는 여성을 반드시 지정합니다. 빈 값은 기존 미설정 호실 호환용입니다.",
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


class LodgingRoomScope(models.Model):
    """호실을 사용할 수 있는 지역·부서 범위."""

    room = models.ForeignKey(
        LodgingRoom,
        on_delete=models.CASCADE,
        related_name="scopes",
        verbose_name="호실",
    )
    division = models.ForeignKey(
        "users.Division",
        on_delete=models.PROTECT,
        related_name="retreat_lodging_room_scopes",
        verbose_name="부서",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "수련회 호실 지역·부서 범위"
        verbose_name_plural = "수련회 호실 지역·부서 범위"
        ordering = [
            "room",
            "division__region__sort_order",
            "division__sort_order",
            "id",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["room", "division"],
                name="uniq_lodging_room_scope_room_division",
            )
        ]


class LodgingRoomGroupTarget(models.Model):
    """호실을 사용할 수 있는 특정 조."""

    room = models.ForeignKey(
        LodgingRoom,
        on_delete=models.CASCADE,
        related_name="group_targets",
        verbose_name="호실",
    )
    group = models.ForeignKey(
        "retreat.RetreatGroup",
        on_delete=models.CASCADE,
        related_name="lodging_room_targets",
        verbose_name="조",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "수련회 호실 지정 조"
        verbose_name_plural = "수련회 호실 지정 조"
        ordering = ["room", "group__order", "group__id"]
        constraints = [
            models.UniqueConstraint(
                fields=["room", "group"],
                name="uniq_lodging_room_group_target",
            )
        ]
