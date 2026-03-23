"""팀 단위 출석부 (교시 칩)."""

from __future__ import annotations

import datetime as dt

from django.core.exceptions import ValidationError
from django.db import models

from attendance.choices import ATTENDANCE_CHIP_VALUES
from registry.models import Member
from users.models.audit import AdminAuditFields
from users.models.organization import Team


class TeamAttendanceSession(AdminAuditFields):
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="attendance_sessions",
        verbose_name="팀",
    )
    session_date = models.DateField("날짜")
    title = models.CharField(
        "제목",
        max_length=120,
        blank=True,
        default="",
        help_text="비우면 앱에서 팀명+출석부로 표시",
    )
    period_count = models.PositiveSmallIntegerField(
        "교시 수",
        default=3,
        help_text="1교시·2교시 … (최대 20)",
    )
    period_labels = models.JSONField(
        "교시 라벨",
        default=list,
        blank=True,
        help_text='비우면 ["1교시","2교시",…]',
    )
    notes = models.TextField("메모", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users_teamattendancesession"
        verbose_name = "팀 출석(회차)"
        verbose_name_plural = "팀 출석(회차)"
        ordering = ["-session_date", "team"]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "session_date"],
                name="uniq_team_attendance_team_date",
            ),
        ]

    def __str__(self):
        t = self.title.strip() or f"{self.team.name} 출석부"
        return f"{self.team} · {self.session_date} · {t}"

    def effective_period_labels(self) -> list[str]:
        raw = self.period_labels or []
        n = max(1, min(self.period_count or 1, 20))
        if isinstance(raw, list) and len(raw) >= n:
            return [str(x) for x in raw[:n]]
        return [f"{i}교시" for i in range(1, n + 1)]

    def roster_members(self):
        div_id = self.team.division_id
        return (
            Member.objects.filter(
                is_active=True,
                division_teams__team_id=self.team_id,
                division_teams__division_id=div_id,
            )
            .distinct()
            .order_by("name")
        )

    def clean(self):
        super().clean()
        if self.period_count is not None and (self.period_count < 1 or self.period_count > 20):
            raise ValidationError({"period_count": "1~20 사이여야 합니다."})


def _normalize_picks(raw):
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValidationError({"picks": "리스트 형식이어야 합니다."})
    out: list[str] = []
    for x in raw:
        s = str(x).strip()
        if not s:
            continue
        if s not in ATTENDANCE_CHIP_VALUES:
            raise ValidationError({"picks": f"허용되지 않는 값: {s!r}"})
        if s not in out:
            out.append(s)
    return out


class TeamMemberSlotAttendance(AdminAuditFields):
    session = models.ForeignKey(
        TeamAttendanceSession,
        on_delete=models.CASCADE,
        related_name="slot_rows",
        verbose_name="팀 출석 회차",
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="team_slot_attendances",
        verbose_name="멤버(교적)",
    )
    slot_index = models.PositiveSmallIntegerField("교시 번호", help_text="1 = 1교시")
    picks = models.JSONField("선택(칩)", default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users_teammemberslotattendance"
        verbose_name = "팀 출석 교시(칩)"
        verbose_name_plural = "팀 출석 교시(칩)"
        ordering = ["session", "member__name", "slot_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "member", "slot_index"],
                name="uniq_team_slot_session_member_index",
            ),
        ]

    def __str__(self):
        return f"{self.member} · {self.session} · {self.slot_index}교시 · {self.picks}"

    def clean(self):
        super().clean()
        self.picks = _normalize_picks(self.picks)
        if self.session_id and self.slot_index:
            sess = getattr(self, "session", None)
            if sess is not None:
                n = sess.period_count
            else:
                n = (
                    TeamAttendanceSession.objects.filter(pk=self.session_id).values_list(
                        "period_count", flat=True
                    ).first()
                    or 3
                )
            if self.slot_index < 1 or self.slot_index > n:
                raise ValidationError({"slot_index": f"1~{n} 이어야 합니다."})


class TeamAttendanceEntryStatus(models.TextChoices):
    NOT_ENTERED = "not_entered", "미입력"
    PARTIAL = "partial", "부분 입력"
    COMPLETE = "complete", "완료"


def member_entry_status(session: TeamAttendanceSession, member_id: int) -> str:
    n = max(1, min(session.period_count, 20))
    rows = TeamMemberSlotAttendance.objects.filter(
        session=session,
        member_id=member_id,
    ).values_list("slot_index", "picks")
    filled = 0
    for _si, picks in rows:
        if picks:
            filled += 1
    if filled == 0:
        return TeamAttendanceEntryStatus.NOT_ENTERED
    if filled < n:
        return TeamAttendanceEntryStatus.PARTIAL
    return TeamAttendanceEntryStatus.COMPLETE


def session_roster_stats(session: TeamAttendanceSession) -> dict:
    members = list(session.roster_members().values_list("pk", flat=True))
    total = len(members)
    complete = partial = not_entered = 0
    for mid in members:
        st = member_entry_status(session, mid)
        if st == TeamAttendanceEntryStatus.COMPLETE:
            complete += 1
        elif st == TeamAttendanceEntryStatus.PARTIAL:
            partial += 1
        else:
            not_entered += 1
    return {
        "total": total,
        "complete": complete,
        "partial": partial,
        "not_entered": not_entered,
    }
