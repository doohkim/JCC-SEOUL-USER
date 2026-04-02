from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from attendance.services.parking import korea_today, parking_request_allowed_now
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
    permit_date = models.DateField(
        "등록 기준일(한국)",
        db_index=True,
        help_text="한국 달력 기준 하루 1회 신청을 구분하는 날짜입니다.",
    )
    created_at = models.DateTimeField("신청일시", auto_now_add=True)
    updated_at = models.DateTimeField("수정일시", auto_now=True)

    class Meta:
        verbose_name = "주차권 신청"
        verbose_name_plural = "주차권 신청"
        ordering = ["-permit_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "vehicle_number", "permit_date"],
                name="unique_user_vehicle_permit_date",
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

        if self._state.adding and self.permit_date is None:
            self.permit_date = korea_today()

        if self.user_id and self.permit_date:
            qs = ParkingPermitApplication.objects.filter(
                user_id=self.user_id,
                vehicle_number=self.vehicle_number,
                permit_date=self.permit_date,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    "이미 해당 날짜에 같은 차량번호로 신청하셨습니다. 하루에 한 번만 신청할 수 있습니다."
                )

        # ModelForm 검증 단계에서는 user/division이 아직 주입되기 전일 수 있다.
        # 실제 신청 저장 직전에 full_clean()을 다시 호출하므로, 그 시점에 시간창을 강제한다.
        if self._state.adding and self.user_id and self.division_id:
            ok, window_msg = parking_request_allowed_now(self.division_id)
            if not ok:
                raise ValidationError(window_msg)

    def save(self, *args, **kwargs):
        if self._state.adding and self.permit_date is None:
            self.permit_date = korea_today()
        super().save(*args, **kwargs)
