"""수련회 조 및 조 운영진 멤버십."""

from __future__ import annotations

import re

from django.conf import settings
from django.db import models

from .event import RetreatEvent


_LEADING_NUM_RE = re.compile(r"^\s*(\d+)")


def _derive_order_from_name(name: str) -> int:
    """'1조'·'10조'처럼 이름 앞자리 숫자를 정렬키로 추출."""
    match = _LEADING_NUM_RE.match(name or "")
    return int(match.group(1)) if match else 0


class RetreatGroup(models.Model):
    """행사·지역·부서별 조(예: 서울 청년부 1조)."""

    event = models.ForeignKey(
        RetreatEvent,
        on_delete=models.CASCADE,
        related_name="groups",
        verbose_name="행사",
    )
    region = models.ForeignKey(
        "users.Region",
        on_delete=models.PROTECT,
        related_name="retreat_groups",
        verbose_name="지역",
    )
    division = models.ForeignKey(
        "users.Division",
        on_delete=models.PROTECT,
        related_name="retreat_groups",
        verbose_name="부서",
    )
    name = models.CharField("조 이름", max_length=50, help_text="예: '1조'")
    order = models.PositiveSmallIntegerField("정렬 순서", default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retreat_groups_created",
        verbose_name="생성자",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "수련회 조"
        verbose_name_plural = "수련회 조"
        ordering = ["event", "order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "name"],
                name="uniq_retreat_group_event_name",
            )
        ]

    def __str__(self) -> str:
        return f"{self.event.name} · {self.region.name} {self.division.name} · {self.name}"

    def save(self, *args, **kwargs):
        if not self.order:
            self.order = _derive_order_from_name(self.name)
        super().save(*args, **kwargs)

    def scope_pairs(self) -> set[tuple[int, int]]:
        """대표 + 보조 (지역, 부서) 쌍 집합."""
        pairs = {(self.region_id, self.division_id)}
        for scope in self.extra_scopes.all():
            pairs.add((scope.region_id, scope.division_id))
        return pairs


class RetreatGroupScope(models.Model):
    """조의 보조 지역·부서 (대표 region/division 외 추가 범위)."""

    group = models.ForeignKey(
        RetreatGroup,
        on_delete=models.CASCADE,
        related_name="extra_scopes",
        verbose_name="조",
    )
    region = models.ForeignKey(
        "users.Region",
        on_delete=models.PROTECT,
        related_name="retreat_group_extra_scopes",
        verbose_name="지역",
    )
    division = models.ForeignKey(
        "users.Division",
        on_delete=models.PROTECT,
        related_name="retreat_group_extra_scopes",
        verbose_name="부서",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "수련회 조 보조 범위"
        verbose_name_plural = "수련회 조 보조 범위"
        ordering = ["group", "region__sort_order", "division__sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "region", "division"],
                name="uniq_retreat_group_scope_group_region_division",
            )
        ]

    def __str__(self) -> str:
        return f"{self.group.name} · {self.region.name} {self.division.name}"


class RetreatGroupMembership(models.Model):
    """조장·부조장 등 조 운영진(앱 사용자)."""

    class Role(models.TextChoices):
        LEADER = "leader", "조장"
        VICE_LEADER = "vice_leader", "부조장"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="retreat_group_memberships",
        verbose_name="사용자",
    )
    group = models.ForeignKey(
        RetreatGroup,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="조",
    )
    role = models.CharField(
        "역할",
        max_length=20,
        choices=Role.choices,
        default=Role.LEADER,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "조 운영진"
        verbose_name_plural = "조 운영진"
        ordering = ["group", "role", "user"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "user"],
                name="uniq_retreat_group_membership_group_user",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user.username} · {self.get_role_display()} @ {self.group.name}"
