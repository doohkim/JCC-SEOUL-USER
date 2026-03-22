"""직급/권한 레벨 (목사, 전도사 등)."""

from django.db import models


class RoleLevel(models.Model):
    """
    직급/권한 레벨. 노출 범위 결정.
    예: 목사 > 전도사 > 부장 > 일반
    """

    name = models.CharField("직급명", max_length=50)
    code = models.SlugField("코드", max_length=30, unique=True)
    level = models.PositiveSmallIntegerField(
        "레벨",
        default=0,
        help_text="숫자 클수록 상위 권한. 목사=100, 전도사=80, 부장=60, 일반=0",
    )
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)

    class Meta:
        verbose_name = "직급/권한"
        verbose_name_plural = "직급/권한"
        ordering = ["-level", "sort_order"]

    def __str__(self):
        return self.name
