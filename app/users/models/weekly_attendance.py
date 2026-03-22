"""
주간 출석부 (매주 자동 생성되는 ``AttendanceWeek`` + 기록).

- **수요·토요**: 참석 / 불참 / 온라인 (``MidweekAttendanceRecord``)
- **주일**: 서울·인천·지교회·온라인 + 부(1~4) 등 상세 (``SundayAttendanceLine``, 행 여러 개 가능)

엑셀 일괄 스냅샷은 ``WorshipRosterScope`` / ``WorshipRosterEntry`` 를 계속 사용할 수 있습니다.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from ..choices.attendance import (
    MidweekAttendanceStatus,
    MidweekServiceType,
    WorshipVenue,
)
from .audit import AdminAuditFields
from .member import Member
from .organization import Division, Team

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


class AttendanceWeek(AdminAuditFields):
    """
    한 부서·한 주(주일 기준) 출석부 껍데기.

    ``week_sunday`` 는 그 주를 대표하는 **주일 날짜** (한국 달력 기준으로 관리 권장).
    """

    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        related_name="attendance_weeks",
        verbose_name="부서",
    )
    week_sunday = models.DateField(
        "기준 주일",
        help_text="이 출석 주차를 식별하는 주일 날짜(해당 주의 주일).",
    )
    note = models.CharField("비고", max_length=200, blank=True, default="")
    auto_created = models.BooleanField(
        "자동 생성됨",
        default=False,
        help_text="ensure_weekly_attendance_weeks 등으로 생성된 경우 True",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "주간 출석(주차)"
        verbose_name_plural = "주간 출석(주차)"
        ordering = ["-week_sunday", "division"]
        constraints = [
            models.UniqueConstraint(
                fields=["division", "week_sunday"],
                name="uniq_attendance_week_division_sunday",
            ),
        ]

    def __str__(self):
        return f"{self.division.name} · {self.week_sunday} 주간"


class MidweekAttendanceRecord(AdminAuditFields):
    """수요일 또는 토요일 예배 출석 한 건."""

    week = models.ForeignKey(
        AttendanceWeek,
        on_delete=models.CASCADE,
        related_name="midweek_records",
        verbose_name="주차",
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
        verbose_name = "수·토 출석"
        verbose_name_plural = "수·토 출석"
        ordering = ["week", "service_type", "member__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["week", "member", "service_type"],
                name="uniq_midweek_week_member_service",
            ),
        ]

    def __str__(self):
        st = self.get_status_display() if self.status else "(미입력)"
        return f"{self.member.name} · {self.get_service_type_display()} · {st}"


class SundayAttendanceLine(AdminAuditFields):
    """
    주일 예배 출석 한 줄.

    같은 주에 서울 1부·2부 등 여러 줄 허용 → ``week``+``member``+``venue``+``session_part``+``branch_label`` 유일.
    """

    week = models.ForeignKey(
        AttendanceWeek,
        on_delete=models.CASCADE,
        related_name="sunday_lines",
        verbose_name="주차",
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "주일 출석(행)"
        verbose_name_plural = "주일 출석(행)"
        ordering = ["week", "member__name", "venue", "session_part"]
        constraints = [
            models.UniqueConstraint(
                fields=["week", "member", "venue", "session_part", "branch_label"],
                name="uniq_sunday_line_week_member_venue_part_branch",
            ),
        ]

    def __str__(self):
        part = f"{self.session_part}부" if self.session_part else ""
        br = f" · {self.branch_label}" if self.branch_label else ""
        return f"{self.member.name} · {self.week.week_sunday} · {self.get_venue_display()} {part}{br}"

    def clean(self):
        super().clean()
        if self.member_id is None or self.week_id is None:
            return
        if self.team_id:
            div_id = self.week.division_id
            if self.team.division_id != div_id:
                raise ValidationError(
                    {"team": "팀이 이 출석 주차의 부서와 맞지 않습니다."}
                )

        others = SundayAttendanceLine.objects.filter(
            week_id=self.week_id,
            member_id=self.member_id,
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
                            "같은 주·같은 부(시각)에 인천과 서울 주일 출석을 동시에 둘 수 없습니다."
                        ]
                    }
                )
            if others.filter(venue__in=_REMOTE_VENUES).exists():
                raise ValidationError(
                    {
                        "__all__": [
                            "같은 주에 주일 현장(인천/서울 1~4부)과 온라인·지교회 출석 줄을 동시에 둘 수 없습니다."
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
                            "같은 주에 주일 온라인·지교회와 현장(인천/서울 1~4부) 출석 줄을 동시에 둘 수 없습니다."
                        ]
                    }
                )
