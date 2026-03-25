from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from users.models import Division, Team


class ParkingPermitApplication(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "신청"
        APPROVED = "approved", "승인"
        REJECTED = "rejected", "반려"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parking_permit_applications",
        verbose_name="신청자",
    )
    vehicle_number = models.CharField("차량번호", max_length=30)
    division = models.ForeignKey(
        Division,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parking_permit_applications",
        verbose_name="소속 부서",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parking_permit_applications",
        verbose_name="소속 팀",
    )
    status = models.CharField(
        "상태",
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED,
    )
    note = models.CharField("메모", max_length=200, blank=True, default="")
    created_at = models.DateTimeField("신청일시", auto_now_add=True)
    updated_at = models.DateTimeField("수정일시", auto_now=True)

    class Meta:
        verbose_name = "주차권 신청"
        verbose_name_plural = "주차권 신청"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "vehicle_number"],
                name="unique_user_vehicle_number",
            )
        ]

    def __str__(self):
        return f"{self.user.username} · {self.vehicle_number}"

    def clean(self):
        super().clean()
        raw = (self.vehicle_number or "").strip()
        if not raw:
            raise ValidationError({"vehicle_number": "차량번호를 입력해 주세요."})
        compact = "".join(raw.split())
        if len(compact) < 6 or len(compact) > 12:
            raise ValidationError({"vehicle_number": "차량번호 형식이 올바르지 않습니다."})
        self.vehicle_number = compact.upper()
        if self.team_id and self.division_id and self.team.division_id != self.division_id:
            raise ValidationError({"team": "팀은 같은 부서에 속해야 합니다."})
