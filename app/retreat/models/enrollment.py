"""출석부 생성 시점의 조원 스냅샷."""

from __future__ import annotations

from django.db import models

from .attendee import RetreatAttendee
from .event import RetreatSession
from .group import RetreatGroup


class RetreatSessionAttendee(models.Model):
    """출석부에 포함된 조원 스냅샷.

    현재 조원 명단(`RetreatAttendee`)은 운영용으로 계속 수정될 수 있지만,
    이미 만들어진 출석부는 이 모델에 복사된 시점의 이름/조/상태를 사용한다.
    """

    session = models.ForeignKey(
        RetreatSession,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name="출석부",
    )
    source_attendee = models.ForeignKey(
        RetreatAttendee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="session_enrollments",
        verbose_name="원본 조원",
    )
    source_group = models.ForeignKey(
        RetreatGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="session_enrollments",
        verbose_name="원본 조",
    )
    name = models.CharField("이름", max_length=60)
    phone = models.CharField("연락처", max_length=30, blank=True, default="")
    gender = models.CharField(
        "성별",
        max_length=10,
        choices=RetreatAttendee.Gender.choices,
        blank=True,
        default="",
    )
    memo = models.CharField("메모", max_length=200, blank=True, default="")
    check_in_status = models.CharField(
        "입·퇴실",
        max_length=15,
        choices=RetreatAttendee.CheckInStatus.choices,
        default=RetreatAttendee.CheckInStatus.CHECKED_IN,
    )
    group_name = models.CharField("조 이름", max_length=50)
    region_id_snapshot = models.PositiveIntegerField("지역 ID", null=True, blank=True)
    region_name = models.CharField("지역명", max_length=100, blank=True, default="")
    division_id_snapshot = models.PositiveIntegerField("부서 ID", null=True, blank=True)
    division_name = models.CharField("부서명", max_length=100, blank=True, default="")
    member_role = models.CharField(
        "구분",
        max_length=15,
        choices=RetreatAttendee.MemberRole.choices,
        default=RetreatAttendee.MemberRole.MEMBER,
    )
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)
    enrolled_at = models.DateTimeField("스냅샷 생성 일시", auto_now_add=True)

    class Meta:
        verbose_name = "수련회 출석부 조원 스냅샷"
        verbose_name_plural = "수련회 출석부 조원 스냅샷"
        ordering = [
            "session",
            "region_id_snapshot",
            "division_id_snapshot",
            "sort_order",
            "name",
            "id",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "source_attendee"],
                name="uniq_retreat_session_attendee_source",
            )
        ]
        indexes = [
            models.Index(
                fields=["session", "source_group", "sort_order"],
                name="idx_ret_enroll_sess_group",
            ),
            models.Index(
                fields=["session", "region_id_snapshot", "division_id_snapshot"],
                name="idx_ret_enroll_sess_div",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.session.name} · {self.group_name} · {self.name}"

    @classmethod
    def from_attendee(cls, *, session: RetreatSession, attendee: RetreatAttendee):
        group = attendee.group
        return cls(
            session=session,
            source_attendee=attendee,
            source_group=group,
            name=attendee.name,
            phone=attendee.phone,
            gender=attendee.gender,
            memo=attendee.memo,
            check_in_status=attendee.check_in_status,
            member_role=attendee.member_role,
            group_name=group.name,
            region_id_snapshot=group.region_id,
            region_name=getattr(group.region, "name", "") or "",
            division_id_snapshot=group.division_id,
            division_name=getattr(group.division, "name", "") or "",
            sort_order=attendee.sort_order,
        )
