"""집회 운영진 (집회 단위 운영 권한)."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .event import RetreatEvent


class RetreatCouncilMembership(models.Model):
    """집회별 운영진 구성원.

    역할·담당 범위(지역/부서)에 따라 수련회 탭·API 접근 권한이 결정된다.
    """

    class Role(models.TextChoices):
        EVENT_ADMIN = "event_admin", "집회 전체 관리자"
        EVENT_OBSERVER = "event_observer", "집회 전체 관찰자"
        REGION_ADMIN = "region_admin", "지역 관리자"
        REGION_OBSERVER = "region_observer", "지역 관찰자"
        DIVISION_ADMIN = "division_admin", "부서 관리자"
        DIVISION_OBSERVER = "division_observer", "부서 관찰자"
        PICKUP_OBSERVER = "pickup_observer", "픽업 담당 관찰자"

    EVENT_WIDE_ROLES = frozenset(
        {
            Role.EVENT_ADMIN,
            Role.EVENT_OBSERVER,
            Role.PICKUP_OBSERVER,
        }
    )
    REGION_SCOPED_ROLES = frozenset({Role.REGION_ADMIN, Role.REGION_OBSERVER})
    DIVISION_SCOPED_ROLES = frozenset(
        {Role.DIVISION_ADMIN, Role.DIVISION_OBSERVER}
    )

    event = models.ForeignKey(
        RetreatEvent,
        on_delete=models.CASCADE,
        related_name="council_memberships",
        verbose_name="집회",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="retreat_council_memberships",
        verbose_name="사용자",
    )
    role = models.CharField(
        "역할",
        max_length=32,
        choices=Role.choices,
        default=Role.EVENT_ADMIN,
    )
    region = models.ForeignKey(
        "users.Region",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="retreat_staff_memberships",
        verbose_name="담당 지역",
    )
    division = models.ForeignKey(
        "users.Division",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="retreat_staff_memberships",
        verbose_name="담당 부서",
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
        verbose_name = "집회 운영진"
        verbose_name_plural = "집회 운영진"
        ordering = ["event", "role", "user"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "user"],
                name="uniq_retreat_council_event_user",
            )
        ]

    def __str__(self) -> str:
        scope = self.scope_label or "전체"
        return (
            f"{self.event.name} · {self.user.username} · "
            f"{self.get_role_display()} ({scope})"
        )

    @property
    def scope_label(self) -> str:
        if self.division_id:
            div = self.division
            region_name = getattr(getattr(div, "region", None), "name", "") or ""
            div_name = getattr(div, "name", "") or ""
            return f"{region_name} · {div_name}".strip(" ·")
        if self.region_id:
            return getattr(self.region, "name", "") or ""
        return "전체"

    def clean(self) -> None:
        role = self.role
        if role in self.EVENT_WIDE_ROLES:
            if self.region_id or self.division_id:
                raise ValidationError(
                    "집회 전체·픽업 관찰 역할에는 담당 지역/부서를 지정할 수 없습니다."
                )
            return
        if role in self.REGION_SCOPED_ROLES:
            if not self.region_id:
                raise ValidationError("지역 역할에는 담당 지역이 필요합니다.")
            if self.division_id:
                raise ValidationError("지역 역할에는 담당 부서를 지정할 수 없습니다.")
            return
        if role in self.DIVISION_SCOPED_ROLES:
            if not self.division_id:
                raise ValidationError("부서 역할에는 담당 부서가 필요합니다.")
            if self.region_id and self.division_id:
                if self.region_id != self.division.region_id:
                    raise ValidationError(
                        "담당 지역과 부서의 지역이 일치하지 않습니다."
                    )

    def save(self, *args, **kwargs):
        if self.division_id and not self.region_id:
            self.region_id = self.division.region_id
        self.full_clean()
        super().save(*args, **kwargs)
