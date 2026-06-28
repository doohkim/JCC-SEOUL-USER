"""
앱 사용자 프로필 (본인 회원가입·프로필 작성).

휴대폰 인증: OTP 해시·만료 시각 필드만 두고, 실제 SMS/검증 로직은 뷰/서비스에서 구현.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from .organization import Division, Team
from ..validators import validate_korea_mobile_phone


class UserProfile(models.Model):
    class OnboardingStatus(models.TextChoices):
        PENDING = "pending", "승인 대기"
        APPROVED = "approved", "승인 완료"
        REJECTED = "rejected", "반려"

    class ApplicantRole(models.TextChoices):
        MEMBER = "member", "성도"
        PASTOR = "pastor", "목사"
        EVANGELIST = "evangelist", "전도사"

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
    avatar_user_uploaded = models.BooleanField(
        "사용자 업로드 프로필 이미지",
        default=False,
        help_text="프로필 페이지에서 직접 올린 이미지만 화면에 표시한다.",
    )
    bio = models.TextField("소개", blank=True, default="")
    interest_topics = models.CharField(
        "관심 주제",
        max_length=500,
        blank=True,
        default="",
        help_text="쉼표로 구분된 관심 주제 태그",
    )
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
    requested_applicant_role = models.CharField(
        "신청 직급",
        max_length=20,
        choices=ApplicantRole.choices,
        default=ApplicantRole.MEMBER,
        help_text="가입 신청서 구분용(목사/전도사/성도). User.role_level 과 별개.",
    )
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
        if self.user is not None:
            return f"Profile · {self.user.username}"
        label = (self.real_name or self.display_name or "").strip() or "?"
        return f"Profile · {label} (계정 없음)"

    @property
    def interest_topic_list(self) -> list[str]:
        if not self.interest_topics:
            return []
        return [t.strip() for t in self.interest_topics.split(",") if t.strip()]

    def clean(self):
        super().clean()
        # 신청 부서가 바뀌면 부서와 어긋난 신청 팀/희망 조는 비워 정합성을 유지한다.
        # (부서 변경을 막지 않도록 폼에 없는 필드로 에러를 던지지 않는다.)
        if (
            self.requested_team_id
            and self.requested_division_id
            and self.requested_team.division_id != self.requested_division_id
        ):
            self.requested_team = None
        if (
            self.requested_retreat_group_id
            and self.requested_division_id
            and self.requested_retreat_group.division_id != self.requested_division_id
        ):
            self.requested_retreat_group = None
        # 희망 조가 비워졌는데 수련회 참여로 남아 있으면 참여 신청도 함께 해제.
        if self.requested_retreat_participation and not self.requested_retreat_group_id:
            self.requested_retreat_participation = False
            self.requested_retreat_event = None


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
