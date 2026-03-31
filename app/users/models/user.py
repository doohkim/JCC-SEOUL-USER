"""앱 로그인 계정. 프로필·휴대폰 인증은 ``UserProfile``."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """회원가입으로 생성. 조직 소속은 ``UserDivisionTeam`` 등으로 ``User`` 에 연결."""

    role_level = models.ForeignKey(
        "RoleLevel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="직급/권한",
        help_text="목사/전도사/부장 등 → Admin·API 노출 범위",
    )
    can_manage_attendance = models.BooleanField(
        "출석 관리 권한",
        default=False,
        help_text="팀장 출석/출석부 관리 화면 접근 권한",
    )
    can_manage_parking = models.BooleanField(
        "주차 관리 권한",
        default=False,
        help_text="주차권/주차 운영 관리 화면 접근 권한",
    )
    can_manage_accounts = models.BooleanField(
        "계정 관리 권한",
        default=False,
        help_text="부서 계정 직책 관리 화면 접근 권한",
    )

    class Meta:
        verbose_name = "사용자(계정)"
        verbose_name_plural = "사용자(계정)"

    def __str__(self):
        try:
            p = self.profile
            if p.display_name:
                return f"{self.username} · {p.display_name}"
        except Exception:
            pass
        return self.username
