"""상담 예약·신청 모델."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class CounselorScheduleSettings(models.Model):
    """
    상담사별 기본 슬롯 템플릿.
    기본: 매일 start_hour~end_hour(마지막 슬롯 종료 시각), slot_duration_minutes 간격.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="counselor_schedule_settings",
        verbose_name="상담사",
    )
    slot_duration_minutes = models.PositiveSmallIntegerField("슬롯 길이(분)", default=60)
    default_start_hour = models.PositiveSmallIntegerField("기본 시작 시", default=10)
    default_end_hour = models.PositiveSmallIntegerField(
        "기본 종료 시(마지막 슬롯이 이 시각에 끝남)",
        default=23,
        help_text="예: 23이면 22:00~23:00 슬롯까지 생성",
    )
    weekday_hours_json = models.JSONField(
        "요일별 시간(선택)",
        blank=True,
        null=True,
        help_text='예: {"0": {"start": 10, "end": 23}, ...} 월=0',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "상담사 일정 템플릿"
        verbose_name_plural = "상담사 일정 템플릿"

    def __str__(self):
        return f"{self.user_id} schedule template"


class CounselorDayOverride(models.Model):
    """오늘 기준 롤링 창 안의 특정 일자만 템플릿과 다르게."""

    counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="counselor_day_overrides",
        verbose_name="상담사",
    )
    date = models.DateField("날짜")
    is_closed = models.BooleanField("휴무(해당 일 전체)", default=False)
    custom_slots_json = models.JSONField(
        "커스텀 슬롯",
        blank=True,
        null=True,
        help_text='시작 시 정수 리스트 예: [10,11,12] 또는 [["10:00","11:00"], ...]',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "상담사 일별 예약 오버라이드"
        verbose_name_plural = "상담사 일별 예약 오버라이드"
        constraints = [
            models.UniqueConstraint(fields=["counselor", "date"], name="unique_counselor_day_override"),
        ]

    def __str__(self):
        return f"{self.counselor_id} {self.date}"


class CounselingSlot(models.Model):
    class State(models.TextChoices):
        OPEN = "open", "예약 가능"
        PENDING = "pending", "신청 대기"
        BOOKED = "booked", "확정"
        BLOCKED = "blocked", "차단"

    counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="counseling_slots",
        verbose_name="상담사",
    )
    date = models.DateField("날짜")
    start_time = models.TimeField("시작")
    end_time = models.TimeField("종료")
    state = models.CharField(
        "상태",
        max_length=16,
        choices=State.choices,
        default=State.OPEN,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "상담 슬롯"
        verbose_name_plural = "상담 슬롯"
        constraints = [
            models.UniqueConstraint(
                fields=["counselor", "date", "start_time"],
                name="unique_counselor_date_start",
            ),
        ]
        indexes = [
            models.Index(fields=["counselor", "date", "state"]),
        ]

    def __str__(self):
        return f"{self.counselor_id} {self.date} {self.start_time}-{self.end_time} {self.state}"


class CounselingRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "대기"
        ACCEPTED = "accepted", "수락"
        REJECTED = "rejected", "거절"
        CANCELLED = "cancelled", "취소"

    public_id = models.UUIDField("공개 ID", default=uuid.uuid4, unique=True, editable=False)
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="counseling_requests_sent",
        verbose_name="신청자",
    )
    counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="counseling_requests_received",
        verbose_name="상담사",
    )
    slot = models.OneToOneField(
        CounselingSlot,
        on_delete=models.PROTECT,
        related_name="counseling_request",
        verbose_name="슬롯",
    )
    status = models.CharField(
        "상태",
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    applicant_message = models.TextField("상담 요청 내용", blank=True)
    counselor_notes_json = models.JSONField(
        "상담 메모(리치 텍스트/Quill delta 등)",
        default=dict,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "상담 신청"
        verbose_name_plural = "상담 신청"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["counselor", "status"]),
            models.Index(fields=["applicant", "status"]),
        ]

    def __str__(self):
        return f"{self.public_id} {self.status}"
