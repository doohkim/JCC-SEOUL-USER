"""
교회 조직·권한 확장 모델.

구조:
- Division(상위 부서): 청년부, 대학부, 중고등부, 철산 교구, 동작 교구 등
- Team(팀): Division 소속, 메인 조직 단위 (팀 > 셀 계층)
- Club(동아리): 중복 소속 가능
- FunctionalDepartment(일하는 부서): 찬양단, 전도부, 멀티미디어부 등
- RoleLevel(직급/권한): 목사, 전도사, 부장, 일반 → "목사님만 보기", "해당 부서만 보기" 등
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """구성원. 인증 + 한글 이름 + 권한 레벨."""

    name_ko = models.CharField("한글 이름", max_length=50)
    role_level = models.ForeignKey(
        "RoleLevel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="직급/권한",
        help_text="목사/전도사/부장 등 → 노출 범위(목사님만 보기, 해당 부서만 보기) 결정",
    )

    class Meta:
        verbose_name = "사용자"
        verbose_name_plural = "사용자"

    def __str__(self):
        return self.name_ko or self.username


# ---------- 권한: 누구에게 무엇을 보여줄지 ----------


class RoleLevel(models.Model):
    """
    직급/권한 레벨. 노출 범위 결정.
    예: 목사 > 전도사 > 부장 > 일반 (목사님만 보기, 전도사님만 보기, 해당 부서만 보기)
    """

    name_ko = models.CharField("직급명", max_length=50)
    code = models.SlugField("코드", max_length=30, unique=True)
    level = models.PositiveSmallIntegerField(
        "레벨",
        default=0,
        help_text="숫자 클수록 상위 권한. 목사=100, 전도사=80, 부장=60, 일반=0",
    )
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)

    class Meta:
        verbose_name = "직급/권한"
        verbose_name_plural = "직급/권한"
        ordering = ["-level", "sort_order"]

    def __str__(self):
        return self.name_ko


# ---------- 상위 부서 (청년부, 대학부, 교구 등) ----------


class Division(models.Model):
    """상위 부서. 청년부, 대학부, 중고등부, 철산 교구, 동작 교구 등."""

    name_ko = models.CharField("이름", max_length=100)
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
        ordering = ["sort_order", "name_ko"]

    def __str__(self):
        return self.name_ko


# ---------- 팀 (해당 부서 내 메인 조직, 사람들이 주로 소속) ----------


class Team(models.Model):
    """팀. Division 소속, 메인 조직 단위. parent로 팀 > 셀 계층."""

    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        related_name="teams",
        verbose_name="소속 부서",
    )
    name_ko = models.CharField("팀명", max_length=100)
    code = models.SlugField("코드", max_length=50, help_text="동일 Division 내에서만 유일하면 됨")
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
        ordering = ["division", "sort_order", "name_ko"]
        unique_together = [["division", "code"]]

    def __str__(self):
        return f"{self.division.name_ko} · {self.name_ko}"


# ---------- 주 소속: 이 부서의 이 팀에 소속 ----------


class UserDivisionTeam(models.Model):
    """사용자의 부서·팀 소속 (메인 소속). 한 사람이 한 부서에 한 팀만 primary 가능."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="division_teams",
        verbose_name="사용자",
    )
    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        related_name="member_division_teams",
        verbose_name="부서",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="member_division_teams",
        verbose_name="팀",
    )
    is_primary = models.BooleanField(
        "주 소속",
        default=False,
        help_text="이 부서에서의 주 소속 팀(한 부서당 하나 권장)",
    )
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "부서·팀 소속"
        verbose_name_plural = "부서·팀 소속"
        ordering = ["user", "-is_primary", "division", "sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "division", "team"],
                name="unique_user_division_team",
            )
        ]

    def __str__(self):
        return f"{self.user.name_ko} @ {self.division.name_ko} · {self.team.name_ko}"

    def save(self, *args, **kwargs):
        if self.team.division_id != self.division_id:
            raise ValueError("team must belong to the same division")
        super().save(*args, **kwargs)


# ---------- 동아리 (중복 소속 가능) ----------


class Club(models.Model):
    """동아리. 사용자는 여러 동아리에 중복 소속 가능."""

    name_ko = models.CharField("이름", max_length=100)
    code = models.SlugField("코드", max_length=50, unique=True)
    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="clubs",
        verbose_name="소속 부서",
        help_text="비우면 교회 전체 동아리",
    )
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)

    class Meta:
        verbose_name = "동아리"
        verbose_name_plural = "동아리"
        ordering = ["division", "sort_order", "name_ko"]

    def __str__(self):
        return self.name_ko


class UserClub(models.Model):
    """사용자-동아리 소속 (중복 소속 가능)."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="clubs",
        verbose_name="사용자",
    )
    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name="members",
        verbose_name="동아리",
    )
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "동아리 소속"
        verbose_name_plural = "동아리 소속"
        unique_together = [["user", "club"]]
        ordering = ["user", "sort_order"]

    def __str__(self):
        return f"{self.user.name_ko} · {self.club.name_ko}"


# ---------- 일하는 부서 (찬양단, 전도부, 멀티미디어부 등) ----------


class FunctionalDepartment(models.Model):
    """일하는 부서. 찬양단, 전도부, 멀티미디어부 등. 중복 소속 가능."""

    name_ko = models.CharField("이름", max_length=100)
    code = models.SlugField("코드", max_length=50, unique=True)
    division = models.ForeignKey(
        Division,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="functional_departments",
        verbose_name="소속 부서",
        help_text="비우면 교회 전체 부서",
    )
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)

    class Meta:
        verbose_name = "일하는 부서"
        verbose_name_plural = "일하는 부서"
        ordering = ["division", "sort_order", "name_ko"]

    def __str__(self):
        return self.name_ko


class Role(models.Model):
    """직책 (회장, 부장, 팀장, 셀장, 단장 등)."""

    name_ko = models.CharField("직책명", max_length=50)
    code = models.SlugField("코드", max_length=30, unique=True)
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)

    class Meta:
        verbose_name = "직책"
        verbose_name_plural = "직책"
        ordering = ["sort_order", "name_ko"]

    def __str__(self):
        return self.name_ko


class UserFunctionalDeptRole(models.Model):
    """사용자-일하는 부서-직책. 찬양단 단장, 멀티미디어 부장 등 (중복 소속 가능)."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="functional_dept_roles",
        verbose_name="사용자",
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
        related_name="functional_dept_roles",
        verbose_name="직책",
    )
    sort_order = models.PositiveSmallIntegerField("정렬 순서", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "일하는 부서 직책"
        verbose_name_plural = "일하는 부서 직책"
        ordering = ["user", "functional_department", "sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "functional_department", "role"],
                name="unique_user_funcdept_role",
            )
        ]

    def __str__(self):
        return f"{self.user.name_ko} - {self.role.name_ko} @ {self.functional_department.name_ko}"
