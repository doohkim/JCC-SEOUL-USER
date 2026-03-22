"""예배 출석 명단 스냅샷 (엑셀 임포트)."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

from attendance.choices.attendance import WorshipVenue
from registry.models import Member
from users.models.audit import AdminAuditFields
from users.models.organization import Division, Team

_PHYSICAL_VENUES = frozenset({WorshipVenue.INCHEON, WorshipVenue.SEOUL})
_REMOTE_VENUES = frozenset({WorshipVenue.ONLINE, WorshipVenue.BRANCH})
_PHYSICAL_PARTS = frozenset({1, 2, 3, 4})


def _is_physical_timed_scope(scope) -> bool:
    return scope.venue in _PHYSICAL_VENUES and scope.session_part in _PHYSICAL_PARTS


def _is_remote_scope(scope) -> bool:
    return scope.venue in _REMOTE_VENUES


def opposing_physical_venue(venue: str) -> str | None:
    if venue == WorshipVenue.INCHEON:
        return WorshipVenue.SEOUL
    if venue == WorshipVenue.SEOUL:
        return WorshipVenue.INCHEON
    return None


class WorshipRosterScope(AdminAuditFields):
    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        related_name="worship_roster_scopes",
        verbose_name="부서",
    )
    venue = models.CharField(
        "예배 구분",
        max_length=20,
        choices=WorshipVenue.choices,
    )
    year = models.PositiveSmallIntegerField("연도", help_text="예: 2024")
    session_part = models.PositiveSmallIntegerField(
        "부",
        default=0,
        help_text="1~4부. 인천(미구분 시 기본 3). 온라인/지교회는 0.",
    )
    branch_label = models.CharField(
        "지교회 표기",
        max_length=100,
        blank=True,
        default="",
        help_text="지교회일 때 하위 폴더명 등 (서울/인천/온라인은 보통 비움)",
    )
    snapshot_label = models.CharField(
        "스냅샷(시트) 구분",
        max_length=200,
        blank=True,
        default="",
        help_text="한 파일에 주차별 시트가 여러 개일 때 구분.",
    )
    sort_order = models.PositiveSmallIntegerField("정렬", default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users_worshiprosterscope"
        verbose_name = "출석 명단 구분"
        verbose_name_plural = "출석 명단 구분"
        ordering = ["-year", "venue", "session_part", "branch_label", "snapshot_label"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "division",
                    "venue",
                    "year",
                    "session_part",
                    "branch_label",
                    "snapshot_label",
                ],
                name="uniq_worship_roster_scope_div_venue_year_part_branch_snap",
            ),
        ]

    def __str__(self):
        part = f"{self.session_part}부" if self.session_part else "부(해당없음)"
        extra = f" · {self.branch_label}" if self.branch_label else ""
        snap = f" · [{self.snapshot_label}]" if self.snapshot_label else ""
        return f"{self.division.name} · {self.get_venue_display()} · {self.year} · {part}{extra}{snap}"


class WorshipRosterEntry(AdminAuditFields):
    scope = models.ForeignKey(
        WorshipRosterScope,
        on_delete=models.CASCADE,
        related_name="entries",
        verbose_name="명단 구분",
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="worship_roster_entries",
        verbose_name="멤버",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="worship_roster_entries",
        verbose_name="팀",
        help_text="엑셀 팀 열 기준",
    )
    source_rel_path = models.CharField(
        "원본 파일(상대경로)",
        max_length=500,
        blank=True,
        default="",
    )
    sheet_name = models.CharField("시트명", max_length=200, blank=True, default="")
    first_imported_at = models.DateTimeField("최초 반영 시각", auto_now_add=True)
    last_imported_at = models.DateTimeField("마지막 반영 시각", auto_now=True)

    class Meta:
        db_table = "users_worshiprosterentry"
        verbose_name = "출석 명단 구성원"
        verbose_name_plural = "출석 명단 구성원"
        ordering = ["scope", "member__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["scope", "member"],
                name="uniq_worship_roster_entry_scope_member",
            ),
        ]

    def __str__(self):
        return f"{self.member.name} @ {self.scope}"

    def clean(self):
        super().clean()
        if self.member_id is None or self.scope_id is None:
            return
        scope = self.scope

        qs_same_occasion = WorshipRosterEntry.objects.filter(
            member_id=self.member_id,
            scope__division_id=scope.division_id,
            scope__year=scope.year,
            scope__snapshot_label=scope.snapshot_label,
        )
        if self.pk:
            qs_same_occasion = qs_same_occasion.exclude(pk=self.pk)

        if _is_physical_timed_scope(scope):
            other_city = opposing_physical_venue(scope.venue)
            if other_city:
                clash = qs_same_occasion.filter(
                    scope__venue=other_city,
                    scope__session_part=scope.session_part,
                )
                if clash.exists():
                    raise ValidationError(
                        {
                            "__all__": [
                                "같은 연도·같은 부(시각)·같은 스냅샷에서는 인천 예배와 서울 예배에 동시에 올릴 수 없습니다."
                            ]
                        }
                    )

            clash_remote = qs_same_occasion.filter(scope__venue__in=_REMOTE_VENUES)
            if clash_remote.exists():
                raise ValidationError(
                    {
                        "__all__": [
                            "같은 연도·같은 스냅샷에서 인천/서울 현장 예배(1~4부) 명단과 온라인·지교회 명단을 동시에 올릴 수 없습니다."
                        ]
                    }
                )

        elif _is_remote_scope(scope):
            clash_physical = qs_same_occasion.filter(
                scope__venue__in=_PHYSICAL_VENUES,
                scope__session_part__in=_PHYSICAL_PARTS,
            )
            if clash_physical.exists():
                raise ValidationError(
                    {
                        "__all__": [
                            "같은 연도·같은 스냅샷에서 온라인·지교회와 인천/서울 현장 예배(1~4부) 명단을 동시에 올릴 수 없습니다."
                        ]
                    }
                )
