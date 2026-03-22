"""교적 상세 — 목사·전도사 기록용 (연락처·사진·비고 등)."""

from __future__ import annotations

from django.db import models

from ..validators import validate_korea_mobile_phone
from .audit import AdminAuditFields
from .member import Member


class MemberProfile(AdminAuditFields):
    member = models.OneToOneField(
        Member,
        on_delete=models.CASCADE,
        related_name="pastoral_profile",
        verbose_name="멤버(교적)",
    )
    birth_date = models.DateField("생년월일", null=True, blank=True)
    phone = models.CharField(
        "연락처(교적)",
        max_length=30,
        blank=True,
        default="",
        validators=[validate_korea_mobile_phone],
        help_text="교적부용. 앱 프로필 휴대폰과 별개일 수 있음.",
    )
    address = models.TextField("주소", blank=True, default="")
    church_position_display = models.CharField(
        "직분·직책(카드)",
        max_length=100,
        blank=True,
        default="",
    )
    workplace_display = models.CharField(
        "직장(업무)",
        max_length=200,
        blank=True,
        default="",
    )
    photo = models.ImageField(
        "사진",
        upload_to="members/profile/",
        null=True,
        blank=True,
    )
    family_photo = models.ImageField(
        "가족 사진",
        upload_to="members/family/",
        null=True,
        blank=True,
    )
    staff_notes = models.TextField(
        "목회 메모",
        blank=True,
        default="",
        help_text="관리자·목회진만 열람",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "교적 프로필"
        verbose_name_plural = "교적 프로필"

    def __str__(self):
        return f"교적프로필 · {self.member.name}"
