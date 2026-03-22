"""
앱 사용자 프로필 (본인 회원가입·프로필 작성).

휴대폰 인증: OTP 해시·만료 시각 필드만 두고, 실제 SMS/검증 로직은 뷰/서비스에서 구현.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from ..validators import validate_korea_mobile_phone


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="계정",
    )
    display_name = models.CharField(
        "표시 이름",
        max_length=50,
        blank=True,
        default="",
        help_text="앱·관리자에 보이는 이름",
    )
    phone = models.CharField(
        "휴대폰",
        max_length=30,
        blank=True,
        default="",
        validators=[validate_korea_mobile_phone],
    )
    phone_verified = models.BooleanField("휴대폰 인증 완료", default=False)
    phone_verified_at = models.DateTimeField("인증 완료 시각", null=True, blank=True)
    phone_otp_hash = models.CharField(
        "OTP 해시(임시)",
        max_length=128,
        blank=True,
        default="",
        help_text="인증번호 검증용(평문 저장 금지)",
    )
    phone_otp_expires_at = models.DateTimeField("OTP 만료", null=True, blank=True)
    phone_otp_attempts = models.PositiveSmallIntegerField("OTP 시도 횟수", default=0)
    avatar = models.ImageField(
        "프로필 이미지",
        upload_to="users/avatars/",
        null=True,
        blank=True,
    )
    bio = models.TextField("소개", blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "사용자 프로필"
        verbose_name_plural = "사용자 프로필"

    def __str__(self):
        return f"Profile · {self.user.username}"
