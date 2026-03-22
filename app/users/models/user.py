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
