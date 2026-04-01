"""직급/권한 레벨 (목사, 전도사 등)."""

from django.db import models


class RoleLevel(models.Model):
    """
    직급 레벨(교회 직분 서열).
    예: 전도사 > 목사 > 회장 > 부회장 > 총무 > 팀장 > 셀장 > 팀원
    """

    name = models.CharField("직급명", max_length=50)
    code = models.SlugField("코드", max_length=30, unique=True)
    level = models.PositiveSmallIntegerField(
        "레벨",
        default=0,
        help_text="숫자 클수록 상위 직급",
    )
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)

    class Meta:
        verbose_name = "직급"
        verbose_name_plural = "직급"
        ordering = ["-level", "sort_order"]

    def __str__(self):
        return self.name
