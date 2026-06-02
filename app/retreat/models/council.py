"""수련회 회장단 (행사 단위 운영 위원회)."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from .event import RetreatEvent


class RetreatCouncilMembership(models.Model):
    """행사별 회장단 구성원.

    회장단은 출석부(세션) 생성/수정/삭제, 회장단 명단 관리, 변경 이력 조회 등
    행사 운영의 최상위 권한을 가진다.
    """

    class Role(models.TextChoices):
        CHAIRPERSON = "chairperson", "회장"
        VICE_CHAIRPERSON = "vice_chairperson", "부회장"
        SECRETARY = "secretary", "총무"
        MEMBER = "member", "임원"

    event = models.ForeignKey(
        RetreatEvent,
        on_delete=models.CASCADE,
        related_name="council_memberships",
        verbose_name="행사",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="retreat_council_memberships",
        verbose_name="사용자",
    )
    role = models.CharField(
        "역할",
        max_length=20,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    note = models.CharField("메모", max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retreat_council_memberships_created",
        verbose_name="등록자",
    )

    class Meta:
        verbose_name = "수련회 회장단"
        verbose_name_plural = "수련회 회장단"
        ordering = ["event", "role", "user"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "user"],
                name="uniq_retreat_council_event_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.event.name} · {self.user.username} · {self.get_role_display()}"
