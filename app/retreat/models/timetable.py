"""수련회 타임테이블 (집회 일정표)."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from .event import RetreatEvent


class RetreatTimetableEntry(models.Model):
    """집회별 일정표 항목.

    일자 + 시작/종료 시각 + 프로그램명으로 구성되며, 회장단(또는 슈퍼유저)이
    추가·수정·삭제한다.
    """

    event = models.ForeignKey(
        RetreatEvent,
        on_delete=models.CASCADE,
        related_name="timetable_entries",
        verbose_name="집회",
    )
    day = models.DateField("일자")
    start_time = models.TimeField("시작 시각")
    end_day = models.DateField(
        "종료 일자",
        null=True,
        blank=True,
        help_text="종료 시각이 시작 일자와 다를 때만 설정(자정 넘김 등). 비우면 시작 일자와 동일.",
    )
    end_time = models.TimeField("종료 시각", null=True, blank=True)
    title = models.CharField("프로그램명", max_length=120)
    location = models.CharField("장소", max_length=200, blank=True, default="")
    description = models.TextField("설명", blank=True, default="")
    sort_order = models.PositiveSmallIntegerField(
        "정렬",
        default=0,
        help_text="같은 일자·시작 시각일 때 정렬 기준.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retreat_timetable_entries_created",
        verbose_name="등록자",
    )

    class Meta:
        verbose_name = "수련회 타임테이블"
        verbose_name_plural = "수련회 타임테이블"
        ordering = ["day", "start_time", "sort_order", "id"]
        indexes = [
            models.Index(
                fields=["event", "day", "start_time"],
                name="idx_rt_timetable_event_day",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event.name} · {self.day} {self.start_time:%H:%M} · {self.title}"
