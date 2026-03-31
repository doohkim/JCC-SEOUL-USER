"""부서별 주차권 신청 가능 요일·시간대."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from users.models import Division


class ParkingPermitWindow(models.Model):
    """부서마다 요일·시간대로 신청 오픈 구간을 둔다. 같은 부서·같은 요일에 여러 구간(예: 오전/오후) 가능."""

    class Weekday(models.IntegerChoices):
        MONDAY = 0, "월"
        TUESDAY = 1, "화"
        WEDNESDAY = 2, "수"
        THURSDAY = 3, "목"
        FRIDAY = 4, "금"
        SATURDAY = 5, "토"
        SUNDAY = 6, "일"

    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        related_name="parking_permit_windows",
        verbose_name="부서",
    )
    weekday = models.SmallIntegerField(
        "요일",
        choices=Weekday.choices,
        help_text="월=0 … 일=6 (한국 시각 기준 요일과 동일)",
    )
    start_time = models.TimeField("시작 시각")
    end_time = models.TimeField("종료 시각")
    is_active = models.BooleanField("사용", default=True)

    class Meta:
        verbose_name = "주차권 신청 가능 시간"
        verbose_name_plural = "주차권 신청 가능 시간"
        ordering = ["division", "weekday", "start_time"]
        indexes = [
            models.Index(fields=["division", "weekday", "is_active"]),
        ]

    def __str__(self):
        return f"{self.division.code} · {self.get_weekday_display()} {self.start_time}–{self.end_time}"

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("종료 시각은 시작 시각보다 늦어야 합니다.")
