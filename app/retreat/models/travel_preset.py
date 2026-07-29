"""수련회 입·퇴실 차량(웨이브) 프리셋 — 조원 예정 시각 빠른 입력용."""

from __future__ import annotations

from django.core.validators import RegexValidator
from django.db import models

from .event import RetreatEvent


class RetreatTravelPreset(models.Model):
    """집회·부서별 입실/퇴실 예정시각 프리셋 (선발대·본진·버스 등)."""

    class Direction(models.TextChoices):
        ARRIVAL = "arrival", "입실"
        DEPARTURE = "departure", "퇴실"

    event = models.ForeignKey(
        RetreatEvent,
        on_delete=models.CASCADE,
        related_name="travel_presets",
        verbose_name="집회",
    )
    direction = models.CharField(
        "구분",
        max_length=16,
        choices=Direction.choices,
        db_index=True,
    )
    code = models.CharField(
        "코드",
        max_length=40,
        help_text="예: advance, main, late, own_car, bus, bus_after_evening",
    )
    label = models.CharField(
        "표시명",
        max_length=80,
        help_text="엑셀·UI 문구. 예: 7/30 본진, 8/1 버스",
    )
    color = models.CharField(
        "색상",
        max_length=7,
        default="#2563EB",
        validators=[
            RegexValidator(
                regex=r"^#[0-9A-Fa-f]{6}$",
                message="#2563EB 형식의 HEX 색상을 입력하세요.",
            )
        ],
        help_text="Admin 컬러 피커에서 선택하는 프리셋 태그 색상.",
    )
    occurs_at = models.DateTimeField(
        "예정 시각",
        null=True,
        blank=True,
        help_text="버스·본진 등 고정 시각. 자차(수동)는 비워 두고 조원이 달력에서 직접 고름.",
    )
    divisions = models.ManyToManyField(
        "users.Division",
        related_name="retreat_travel_presets",
        blank=True,
        verbose_name="적용 부서",
        help_text="비우면 모든 부서에 노출. 지정 시 해당 부서 조에만 노출.",
    )
    sort_order = models.PositiveSmallIntegerField("정렬", default=0)
    is_active = models.BooleanField("사용", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "수련회 입퇴실 차량 프리셋"
        verbose_name_plural = "수련회 입퇴실 차량 프리셋"
        ordering = ["direction", "sort_order", "id"]
        indexes = [
            models.Index(
                fields=["event", "direction", "is_active"],
                name="idx_rt_travel_preset_event",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "direction", "code"],
                name="uniq_rt_travel_preset_event_dir_code",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event.name} · {self.get_direction_display()} · {self.label}"
