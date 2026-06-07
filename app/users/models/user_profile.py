"""
앱 사용자 프로필 (본인 회원가입·프로필 작성).

휴대폰 인증: OTP 해시·만료 시각 필드만 두고, 실제 SMS/검증 로직은 뷰/서비스에서 구현.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .organization import Division, Team
from ..validators import validate_korea_mobile_phone


class UserProfile(models.Model):
    class OnboardingStatus(models.TextChoices):
        PENDING = "pending", "승인 대기"
        APPROVED = "approved", "승인 완료"
        REJECTED = "rejected", "반려"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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
    real_name = models.CharField(
        "실명",
        max_length=50,
        blank=True,
        default="",
        help_text="본명(관리·승인 화면용)",
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
    onboarding_status = models.CharField(
        "온보딩 상태",
        max_length=20,
        choices=OnboardingStatus.choices,
        default=OnboardingStatus.PENDING,
    )
    requested_division = models.ForeignKey(
        Division,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_user_profiles",
        verbose_name="신청 부서",
    )
    requested_team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_user_profiles",
        verbose_name="신청 팀",
    )
    onboarding_note = models.TextField("온보딩 메모", blank=True, default="")
    requested_retreat_participation = models.BooleanField(
        "수련회 참여 희망",
        default=False,
    )
    requested_retreat_event = models.ForeignKey(
        "retreat.RetreatEvent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_user_profiles",
        verbose_name="희망 수련회",
    )
    requested_retreat_role = models.CharField(
        "수련회 희망 역할",
        max_length=20,
        blank=True,
        default="",
        help_text="participant | leader | vice_leader",
    )
    requested_retreat_group = models.ForeignKey(
        "retreat.RetreatGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_user_profiles",
        verbose_name="희망 수련회 조",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "사용자 프로필"
        verbose_name_plural = "사용자 프로필"

    def __str__(self):
        return f"Profile · {self.user.username}"

    def clean(self):
        super().clean()
        if (
            self.requested_team_id
            and self.requested_division_id
            and self.requested_team.division_id != self.requested_division_id
        ):
            raise ValidationError({"requested_team": "신청 팀은 신청 부서에 속해야 합니다."})
        if (
            self.requested_retreat_group_id
            and self.requested_division_id
            and self.requested_retreat_group.division_id != self.requested_division_id
        ):
            raise ValidationError(
                {"requested_retreat_group": "희망 조는 신청 부서·지역과 일치해야 합니다."}
            )
        if self.requested_retreat_participation and not self.requested_retreat_group_id:
            if self.requested_retreat_event_id:
                raise ValidationError(
                    {"requested_retreat_group": "수련회 참여 시 조를 선택해야 합니다."}
                )


class UserProfileAvatar(models.Model):
    """
    프로필 이미지 히스토리(여러 개 누적 저장용).

    - 동일 이미지(내용 해시 동일)는 중복 저장하지 않음
    - 카카오에서 이미지가 “사라져도” 기존 이미지는 삭제하지 않음
    - 새 이미지(해시가 다름)만 추가 저장
    """

    user_profile = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="avatar_history",
        verbose_name="프로필",
    )
    user_id_snapshot = models.PositiveIntegerField(
        "계정 ID(스냅샷)",
        null=True,
        blank=True,
        db_index=True,
        help_text="계정 삭제 후에도 이력 조회용으로 보존",
    )
    username_snapshot = models.CharField(
        "username(스냅샷)",
        max_length=150,
        blank=True,
        default="",
    )
    image = models.ImageField(
        "프로필 이미지(히스토리)",
        upload_to="users/avatars/",
        null=True,
        blank=True,
    )
    source_url = models.URLField("원본 URL", null=True, blank=True)
    content_hash = models.CharField(
        "이미지 콘텐츠 해시(sha256 hex)",
        max_length=64,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users_userprofileavatar"
        verbose_name = "사용자 프로필 이미지(히스토리)"
        verbose_name_plural = "사용자 프로필 이미지(히스토리)"
        constraints = [
            models.UniqueConstraint(
                fields=["user_profile", "content_hash"],
                name="uniq_userprofile_avatar_content_hash",
            )
        ]

    def _sync_account_snapshots(self) -> None:
        profile = self.user_profile
        if not profile or not profile.user_id:
            return
        user = profile.user
        self.user_id_snapshot = user.id
        self.username_snapshot = user.username or ""

    def save(self, *args, **kwargs):
        self._sync_account_snapshots()
        super().save(*args, **kwargs)

    def __str__(self):
        uname = self.username_snapshot
        if not uname and self.user_profile_id:
            user = getattr(self.user_profile, "user", None)
            if user is not None:
                uname = user.username
        return f"ProfileAvatar · {uname or '?'} · {self.created_at.isoformat()}"
