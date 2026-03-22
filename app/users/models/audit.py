"""
Admin 등에서 수정자 추적용 추상 필드.

``created_by`` / ``updated_by`` 는 관리자 화면 저장 시 채웁니다 (비로그인·스크립트는 null 가능).
"""

from django.conf import settings
from django.db import models


class AdminAuditFields(models.Model):
    """관리자 수정 추적 (abstract)."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="최초 등록자",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="최종 수정자",
    )

    class Meta:
        abstract = True
