"""
교적(교인) 최소 식별 — 목사·전도사가 관리. 상세는 ``MemberProfile``.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from users.models.audit import AdminAuditFields


class Member(AdminAuditFields):
    """교적부 한 명. 앱 가입자와 연결 시 ``linked_user`` 사용."""

    name = models.CharField("이름", max_length=50)
    name_alias = models.CharField(
        "별칭·통칭",
        max_length=50,
        blank=True,
        default="",
    )
    import_key = models.CharField(
        "임포트 키",
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="엑셀 등 병합용",
    )
    linked_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_member_record",
        verbose_name="연결된 앱 계정",
        help_text=(
            "회원가입 계정과 연결 시 사용. 연결되어 있으면 교적의 부서·팀(MemberDivisionTeam) "
            "변경 시 같은 부서 범위에서 UserDivisionTeam 이 자동으로 맞춰집니다."
        ),
    )
    is_active = models.BooleanField("활성", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users_member"
        verbose_name = "교적(멤버)"
        verbose_name_plural = "교적(멤버)"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["import_key"]),
        ]

    def __str__(self):
        if self.name_alias:
            return f"{self.name}({self.name_alias})"
        return self.name
