"""함께보기 FAQ 항목."""

from __future__ import annotations

from django.db import models


class FaqItem(models.Model):
    question = models.CharField("질문", max_length=300)
    answer = models.TextField("답변")
    sort_order = models.PositiveIntegerField("정렬", default=0)
    is_active = models.BooleanField("활성", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "FAQ"
        verbose_name_plural = "FAQ"
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return self.question
