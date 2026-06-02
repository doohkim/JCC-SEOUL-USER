"""수련회 조원(앱 사용자가 아닐 수 있음)."""

from __future__ import annotations

from django.db import models

from .group import RetreatGroup


class RetreatAttendee(models.Model):
    """조에 속한 출석 대상.

    - 앱 로그인 계정과 무관하게 운영진이 명단 입력.
    - 교적(`registry.Member`)이 있으면 source_member 로 연결(보존만, 권한엔 불사용).
    """

    class Gender(models.TextChoices):
        MALE = "male", "남성"
        FEMALE = "female", "여성"
        UNKNOWN = "", "미지정"

    class CheckInStatus(models.TextChoices):
        CHECKED_IN = "checked_in", "입실"
        CHECKED_OUT = "checked_out", "퇴실"
        PENDING = "pending", "입실전"

    group = models.ForeignKey(
        RetreatGroup,
        on_delete=models.CASCADE,
        related_name="attendees",
        verbose_name="조",
    )
    name = models.CharField("이름", max_length=60)
    phone = models.CharField("연락처", max_length=30, blank=True, default="")
    gender = models.CharField(
        "성별",
        max_length=10,
        choices=Gender.choices,
        blank=True,
        default="",
    )
    memo = models.CharField("메모", max_length=200, blank=True, default="")
    check_in_status = models.CharField(
        "입·퇴실",
        max_length=15,
        choices=CheckInStatus.choices,
        default=CheckInStatus.PENDING,
        help_text="입실전·퇴실 상태인 조원은 출석부에서 결석이 기본으로 선택됩니다.",
    )
    expected_check_in_at = models.DateTimeField(
        "예상 입실 시각", null=True, blank=True
    )
    expected_check_out_at = models.DateTimeField(
        "예상 퇴실 시각", null=True, blank=True
    )
    checked_in_at = models.DateTimeField("실제 입실 시각", null=True, blank=True)
    checked_out_at = models.DateTimeField("실제 퇴실 시각", null=True, blank=True)
    source_member = models.ForeignKey(
        "registry.Member",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retreat_attendees",
        verbose_name="교적 연결",
    )
    lodging_room = models.ForeignKey(
        "retreat.LodgingRoom",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendees",
        verbose_name="숙소 호실",
    )
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "수련회 조원"
        verbose_name_plural = "수련회 조원"
        # 사전순(checked_in < checked_out < pending)으로 입실→퇴실→입실전 자연 정렬.
        ordering = ["group", "check_in_status", "sort_order", "name", "id"]

    def __str__(self) -> str:
        return f"{self.group.name} · {self.name}"
