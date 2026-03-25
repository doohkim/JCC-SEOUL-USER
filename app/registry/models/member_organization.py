"""교적(Member)의 부서·팀·동아리·일하는 부서 소속."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from users.models.organization import Club, Division, FunctionalDepartment, Role, Team

from .member import Member


class MemberDivisionTeam(models.Model):
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="division_teams",
        verbose_name="멤버(교적)",
    )
    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        related_name="member_division_teams",
        verbose_name="부서",
    )
    team = models.ForeignKey(
        Team,
        # 팀(Team) 삭제 시에는 소속 행은 유지하고 팀만 "팀 미정"으로 둔다.
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="member_division_teams",
        verbose_name="팀",
    )
    is_primary = models.BooleanField("주 소속", default=False)
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users_memberdivisionteam"
        verbose_name = "교적 부서·팀 소속"
        verbose_name_plural = "교적 부서·팀 소속"
        ordering = ["member", "-is_primary", "division", "sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["member", "division"],
                name="unique_registry_member_division",
            )
        ]

    def __str__(self):
        tl = self.team.name if self.team_id else "(팀 미지정)"
        return f"{self.member.name} @ {self.division.name} · {tl}"

    def clean(self):
        super().clean()
        if self.member_id and self.division_id:
            qs = MemberDivisionTeam.objects.filter(
                member_id=self.member_id,
                division_id=self.division_id,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    {
                        "division": "같은 부서에 서로 다른 팀 행을 둘 수 없습니다. "
                        "한 부서당 한 팀(또는 팀 미지정)만 지정하세요."
                    }
                )

    def save(self, *args, **kwargs):
        if self.team_id and self.team.division_id != self.division_id:
            raise ValueError("team must belong to the same division")
        super().save(*args, **kwargs)


class MemberClub(models.Model):
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="member_clubs",
        verbose_name="멤버(교적)",
    )
    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name="member_club_memberships",
        verbose_name="동아리",
    )
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users_memberclub"
        verbose_name = "교적 동아리 소속"
        verbose_name_plural = "교적 동아리 소속"
        unique_together = [["member", "club"]]
        ordering = ["member", "sort_order"]

    def __str__(self):
        return f"{self.member.name} · {self.club.name}"


class MemberFunctionalDeptRole(models.Model):
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="functional_dept_roles",
        verbose_name="멤버(교적)",
    )
    functional_department = models.ForeignKey(
        FunctionalDepartment,
        on_delete=models.CASCADE,
        related_name="member_roles",
        verbose_name="일하는 부서",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="member_functional_roles",
        verbose_name="직책",
    )
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users_memberfunctionaldeptrole"
        verbose_name = "교적 일하는 부서 직책"
        verbose_name_plural = "교적 일하는 부서 직책"
        ordering = ["member", "functional_department", "sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["member", "functional_department", "role"],
                name="unique_member_funcdept_role",
            )
        ]

    def __str__(self):
        return f"{self.member.name} - {self.role.name} @ {self.functional_department.name}"
