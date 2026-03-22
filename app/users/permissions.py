"""
권한/노출: role_level + **사용자(User)** 의 ``UserDivisionTeam`` 기준.

교적(Member) 목록은 같은 부서 범위로 필터 (목회 데이터).
"""

from .models import Division, Member, RoleLevel, User


def visible_divisions_for(user: User):
    if not user.is_authenticated:
        return Division.objects.none()
    level = getattr(user.role_level, "level", None) or 0
    if level >= 80:
        return Division.objects.all()
    division_ids = user.division_teams.values_list("division_id", flat=True).distinct()
    return Division.objects.filter(pk__in=division_ids)


def can_see_division(user: User, division: Division) -> bool:
    if not user.is_authenticated:
        return False
    level = getattr(user.role_level, "level", None) or 0
    if level >= 80:
        return True
    return user.division_teams.filter(division=division).exists()


def members_visible_to(actor: User, division: Division | None = None):
    """교적 멤버 (부서 범위)."""
    if not actor.is_authenticated:
        return Member.objects.none()
    divisions = visible_divisions_for(actor)
    if division is not None:
        if not can_see_division(actor, division):
            return Member.objects.none()
        divisions = Division.objects.filter(pk=division.pk)
    return Member.objects.filter(
        division_teams__division__in=divisions,
        is_active=True,
    ).distinct()


def users_visible_to(actor: User, division: Division | None = None):
    """앱 사용자 (같은 부서 범위)."""
    if not actor.is_authenticated:
        return User.objects.none()
    divisions = visible_divisions_for(actor)
    if division is not None:
        if not can_see_division(actor, division):
            return User.objects.none()
        divisions = Division.objects.filter(pk=division.pk)
    return User.objects.filter(
        division_teams__division__in=divisions,
        is_active=True,
    ).distinct()


def has_role_level_or_above(user: User, min_level_code: str) -> bool:
    if not user.is_authenticated or not user.role_level_id:
        return False
    try:
        min_level = RoleLevel.objects.get(code=min_level_code)
        return user.role_level.level >= min_level.level
    except RoleLevel.DoesNotExist:
        return False
