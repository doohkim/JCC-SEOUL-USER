"""
조직: 부서(Division), 팀(Team), 동아리, 일하는 부서, 직책.

- **앱 사용자** 소속: ``UserDivisionTeam``, ``UserClub``, ``UserFunctionalDeptRole``
- 교적(Member) 소속은 ``registry`` 앱의 ``MemberDivisionTeam``.
- ``Member.linked_user`` 가 있으면 교적 부서·팀 변경 시 ``registry.services.linked_user_org_sync``
  가 동일 부서 내 ``UserDivisionTeam`` 을 맞춘다(계정 없는 교인은 Member 만 갱신).
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Division(models.Model):
    name = models.CharField("이름", max_length=100)
    code = models.SlugField("코드", max_length=50, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="상위 부서",
    )
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)

    class Meta:
        verbose_name = "상위 부서"
        verbose_name_plural = "상위 부서"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Team(models.Model):
    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        related_name="teams",
        verbose_name="소속 부서",
    )
    name = models.CharField("팀명", max_length=100)
    code = models.SlugField(
        "코드",
        max_length=50,
        help_text="동일 Division 내에서만 유일하면 됨",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="상위 팀(예: 셀)",
    )
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)

    class Meta:
        verbose_name = "팀"
        verbose_name_plural = "팀"
        ordering = ["division", "sort_order", "name"]
        unique_together = [["division", "code"]]

    def __str__(self):
        return f"{self.division.name} · {self.name}"


# --- 앱 사용자(User) 조직 ---


class UserDivisionTeam(models.Model):
    """앱 계정의 부서·팀 소속."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="division_teams",
        verbose_name="사용자",
    )
    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        related_name="user_division_teams",
        verbose_name="부서",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="user_division_teams",
        verbose_name="팀",
    )
    is_primary = models.BooleanField("주 소속", default=False)
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "사용자 부서·팀 소속"
        verbose_name_plural = "사용자 부서·팀 소속"
        ordering = ["user", "-is_primary", "division", "sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "division"],
                name="unique_users_user_division",
            )
        ]

    def __str__(self):
        tl = self.team.name if self.team_id else "(팀 미지정)"
        return f"{self.user.username} @ {self.division.name} · {tl}"

    def clean(self):
        super().clean()
        if self.user_id and self.division_id:
            qs = UserDivisionTeam.objects.filter(
                user_id=self.user_id,
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


class PastoralDivisionAssignment(models.Model):
    """목사/전도사 담당 부서 매핑(다중 담당 허용)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pastoral_divisions",
        verbose_name="사용자",
    )
    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        related_name="pastoral_assignees",
        verbose_name="담당 부서",
    )
    is_primary = models.BooleanField("주 담당", default=False)
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "목회 담당 부서"
        verbose_name_plural = "목회 담당 부서"
        ordering = ["user", "-is_primary", "sort_order", "division__sort_order", "division__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "division"],
                name="unique_pastoral_user_division",
            )
        ]

    def __str__(self):
        return f"{self.user.username} · {self.division.name}"


class Club(models.Model):
    name = models.CharField("이름", max_length=100)
    code = models.SlugField("코드", max_length=50, unique=True)
    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="clubs",
        verbose_name="소속 부서",
    )
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)

    class Meta:
        verbose_name = "동아리"
        verbose_name_plural = "동아리"
        ordering = ["division", "sort_order", "name"]

    def __str__(self):
        return self.name


class UserClub(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="clubs",
        verbose_name="사용자",
    )
    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name="user_memberships",
        verbose_name="동아리",
    )
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "사용자 동아리 소속"
        verbose_name_plural = "사용자 동아리 소속"
        unique_together = [["user", "club"]]
        ordering = ["user", "sort_order"]

    def __str__(self):
        return f"{self.user.username} · {self.club.name}"


class FunctionalDepartment(models.Model):
    name = models.CharField("이름", max_length=100)
    code = models.SlugField("코드", max_length=50, unique=True)
    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="functional_departments",
        verbose_name="소속 부서",
    )
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)

    class Meta:
        verbose_name = "일하는 부서"
        verbose_name_plural = "일하는 부서"
        ordering = ["division", "sort_order", "name"]

    def __str__(self):
        return self.name


class Role(models.Model):
    name = models.CharField("직책명", max_length=50)
    code = models.SlugField("코드", max_length=30, unique=True)
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)

    class Meta:
        verbose_name = "직책"
        verbose_name_plural = "직책"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class UserFunctionalDeptRole(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="functional_dept_roles",
        verbose_name="사용자",
    )
    functional_department = models.ForeignKey(
        FunctionalDepartment,
        on_delete=models.CASCADE,
        related_name="user_member_roles",
        verbose_name="일하는 부서",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="user_functional_roles",
        verbose_name="직책",
    )
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "사용자 일하는 부서 직책"
        verbose_name_plural = "사용자 일하는 부서 직책"
        ordering = ["user", "functional_department", "sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "functional_department", "role"],
                name="unique_user_funcdept_role",
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.role.name} @ {self.functional_department.name}"
