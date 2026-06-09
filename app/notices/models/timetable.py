"""사이트 전역 타임테이블(일정표)."""

from __future__ import annotations

from django.db import models


class TimetableEntry(models.Model):
    day = models.DateField("일자")
    start_time = models.TimeField("시작")
    end_time = models.TimeField("종료", null=True, blank=True)
    title = models.CharField("제목", max_length=200)
    location = models.CharField("장소", max_length=120, blank=True, default="")
    description = models.TextField("설명", blank=True, default="")
    sort_order = models.PositiveIntegerField("정렬", default=0)

    class Meta:
        verbose_name = "타임테이블"
        verbose_name_plural = "타임테이블"
        ordering = ["day", "start_time", "sort_order", "id"]

    def __str__(self) -> str:
        return f"{self.day} {self.start_time} {self.title}"
