"""예배별 출석: 수요·토요·주일 행은 ``division`` + ``service_date`` 로 식별. 주차는 집계 시에만 계산."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from attendance.choices.attendance import (
    MidweekAttendanceStatus,
    MidweekServiceType,
    WorshipVenue,
)
from registry.models import Member
from users.models.audit import AdminAuditFields
from users.models.organization import Division, Team

_PHYSICAL_VENUES = frozenset({WorshipVenue.INCHEON, WorshipVenue.SEOUL})
_REMOTE_VENUES = frozenset({WorshipVenue.ONLINE, WorshipVenue.BRANCH})
_PHYSICAL_PARTS = frozenset({1, 2, 3, 4})


def _is_physical_timed(venue: str, session_part: int) -> bool:
    return venue in _PHYSICAL_VENUES and session_part in _PHYSICAL_PARTS


def _is_remote(venue: str) -> bool:
    return venue in _REMOTE_VENUES


def _opposing_city(venue: str) -> str | None:
    if venue == WorshipVenue.INCHEON:
        return WorshipVenue.SEOUL
    if venue == WorshipVenue.SEOUL:
        return WorshipVenue.INCHEON
    return None


class MidweekAttendanceRecord(AdminAuditFields):
    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        related_name="midweek_attendance_records",
        verbose_name="부서",
    )
    service_date = models.DateField(
        "예배일",
        help_text="실제 수요·토요 예배가 열린 날짜.",
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="midweek_attendance_records",
        verbose_name="멤버",
    )
    service_type = models.CharField(
        "예배",
        max_length=20,
        choices=MidweekServiceType.choices,
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="midweek_attendance_records",
        verbose_name="팀",
    )
    team_name_snapshot = models.CharField(
        "팀명 스냅샷",
        max_length=100,
        blank=True,
        default="",
        help_text="출석 등록 당시의 팀명. 이후 소속 변경과 무관하게 유지.",
    )
    status = models.CharField(
        "출석",
        max_length=20,
        choices=MidweekAttendanceStatus.choices,
        null=True,
        blank=True,
        help_text="비우면 아직 미입력",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users_midweekattendancerecord"
        verbose_name = "수요·토요 출석"
        verbose_name_plural = "수요·토요 출석"
        ordering = ["-service_date", "service_type", "member__name"]
        indexes = [
            models.Index(fields=["division", "service_date"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["division", "member", "service_type", "service_date"],
                name="uniq_midweek_div_member_service_date",
            ),
        ]

    def __str__(self):
        st = self.get_status_display() if self.status else "(미입력)"
        return (
            f"{self.member.name} · {self.service_date} "
            f"{self.get_service_type_display()} · {st}"
        )

    def clean(self):
        super().clean()
        if self.team_id and self.team.division_id != self.division_id:
            raise ValidationError({"team": "팀이 이 출석의 부서와 맞지 않습니다."})
        if self.service_date:
            if self.service_type == MidweekServiceType.WEDNESDAY:
                if self.service_date.weekday() != 2:
                    raise ValidationError(
                        {"service_date": "수요 예배일은 수요일이어야 합니다."}
                    )
            elif self.service_type == MidweekServiceType.SATURDAY:
                if self.service_date.weekday() != 5:
                    raise ValidationError(
                        {"service_date": "토요 예배일은 토요일이어야 합니다."}
                    )


class SundayAttendanceLine(AdminAuditFields):
    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        related_name="sunday_attendance_lines_division",
        verbose_name="부서",
    )
    service_date = models.DateField(
        "주일 예배일",
        help_text="해당 주일 예배가 열린 날짜(시트 상 날짜).",
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="sunday_attendance_lines",
        verbose_name="멤버",
    )
    venue = models.CharField(
        "주일 구분",
        max_length=20,
        choices=WorshipVenue.choices,
    )
    session_part = models.PositiveSmallIntegerField(
        "부",
        default=0,
        help_text="서울/인천 1~4부. 온라인·지교회는 0.",
    )
    branch_label = models.CharField(
        "지교회 표기",
        max_length=100,
        blank=True,
        default="",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sunday_attendance_lines",
        verbose_name="팀",
    )
    team_name_snapshot = models.CharField(
        "팀명 스냅샷",
        max_length=100,
        blank=True,
        default="",
        help_text="출석 등록 당시의 팀명. 이후 소속 변경과 무관하게 유지.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users_sundayattendanceline"
        verbose_name = "주일 출석(행)"
        verbose_name_plural = "주일 출석(행)"
        ordering = ["-service_date", "member__name", "venue", "session_part"]
        indexes = [
            models.Index(fields=["division", "service_date"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "division",
                    "member",
                    "venue",
                    "session_part",
                    "branch_label",
                    "service_date",
                ],
                name="uniq_sunday_div_member_venue_part_branch_date",
            ),
        ]

    def __str__(self):
        part = f"{self.session_part}부" if self.session_part else ""
        br = f" · {self.branch_label}" if self.branch_label else ""
        return (
            f"{self.member.name} · {self.service_date} · "
            f"{self.get_venue_display()} {part}{br}"
        )

    def clean(self):
        super().clean()
        if self.service_date and self.service_date.weekday() != 6:
            raise ValidationError(
                {"service_date": "주일 예배일은 일요일이어야 합니다."}
            )
        if self.member_id is None or self.division_id is None:
            return
        if self.team_id:
            if self.team.division_id != self.division_id:
                raise ValidationError(
                    {"team": "팀이 이 출석의 부서와 맞지 않습니다."}
                )

        others = SundayAttendanceLine.objects.filter(
            division_id=self.division_id,
            member_id=self.member_id,
            service_date=self.service_date,
        )
        if self.pk:
            others = others.exclude(pk=self.pk)

        v, p = self.venue, self.session_part

        if _is_physical_timed(v, p):
            oc = _opposing_city(v)
            if oc and others.filter(venue=oc, session_part=p).exists():
                raise ValidationError(
                    {
                        "__all__": [
                            "같은 주일·같은 부(시각)에 인천과 서울 주일 출석을 동시에 둘 수 없습니다."
                        ]
                    }
                )
            if others.filter(venue__in=_REMOTE_VENUES).exists():
                raise ValidationError(
                    {
                        "__all__": [
                            "같은 주일에 주일 현장(인천/서울 1~4부)과 온라인·지교회 출석 줄을 동시에 둘 수 없습니다."
                        ]
                    }
                )
        elif _is_remote(v):
            if others.filter(
                venue__in=_PHYSICAL_VENUES,
                session_part__in=_PHYSICAL_PARTS,
            ).exists():
                raise ValidationError(
                    {
                        "__all__": [
                            "같은 주일에 주일 온라인·지교회와 현장(인천/서울 1~4부) 출석 줄을 동시에 둘 수 없습니다."
                        ]
                    }
                )
