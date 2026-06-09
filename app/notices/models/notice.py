"""사이트 전역/지역·부서 공지사항."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Notice(models.Model):
    class Scope(models.TextChoices):
        ALL = "all", "전체"
        DIVISION = "division", "지역·부서"

    title = models.CharField("제목", max_length=200)
    body = models.TextField("내용")
    is_pinned = models.BooleanField("상단 고정", default=False)
    scope = models.CharField(
        "공개 범위",
        max_length=16,
        choices=Scope.choices,
        default=Scope.ALL,
    )
    division = models.ForeignKey(
        "users.Division",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notices",
        verbose_name="대상 부서",
        help_text="공개 범위가 '지역·부서'일 때 대상 부서. '전체'면 비워 둔다.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notices_created",
        verbose_name="작성자",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "공지사항"
        verbose_name_plural = "공지사항"
        ordering = ["-is_pinned", "-created_at"]

    def __str__(self) -> str:
        return self.title

    @property
    def target_label(self) -> str:
        if self.scope == self.Scope.ALL or not self.division_id:
            return "전체"
        return str(self.division)

    @classmethod
    def visible_queryset(cls, *, region_id=None, division_id=None):
        """전체 공지 + (선택한 지역·부서에 해당하는) 공지만 노출.

        - division_id: 해당 부서 공지 + 전체 공지
        - region_id(부서 미선택): 해당 지역 내 모든 부서 공지 + 전체 공지
        - 둘 다 없음: 전체(superuser 관리용) — 모든 공지
        """
        qs = cls.objects.select_related(
            "created_by", "division", "division__region"
        )
        if division_id:
            return qs.filter(
                models.Q(scope=cls.Scope.ALL) | models.Q(division_id=division_id)
            )
        if region_id:
            return qs.filter(
                models.Q(scope=cls.Scope.ALL)
                | models.Q(division__region_id=region_id)
            )
        return qs
