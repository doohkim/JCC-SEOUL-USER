"""
권한/노출 범위: 해당 부서만 보기, 목사님만 보기, 전도사님만 보기 등.

- role_level.level 으로 상위 권한 여부 판단 (목사 > 전도사 > 부장 > 일반)
- 소속 Division 은 UserDivisionTeam 으로 조회
"""

from .models import Division, RoleLevel, User


def visible_divisions_for(user: User):
    """
    이 사용자가 조회할 수 있는 상위 부서(Division) queryset.
    - 목사/전도사 등 상위 권한: 전체 부서 조회 가능 (Division.objects.all())
    - 일반/부장 등: 본인이 소속된 부서만 (user.division_teams.values_list("division", flat=True))
    """
    if not user.is_authenticated:
        return Division.objects.none()
    level = getattr(user.role_level, "level", None) or 0
    # 목사(100), 전도사(80) 수준이면 전체 부서 노출
    if level >= 80:
        return Division.objects.all()
    # 그 외: 본인 소속 부서만
    division_ids = user.division_teams.values_list("division_id", flat=True).distinct()
    return Division.objects.filter(pk__in=division_ids)


def can_see_division(user: User, division: Division) -> bool:
    """이 사용자가 해당 부서를 조회할 수 있는지."""
    if not user.is_authenticated:
        return False
    level = getattr(user.role_level, "level", None) or 0
    if level >= 80:
        return True
    return user.division_teams.filter(division=division).exists()


def users_visible_to(actor: User, division: Division | None = None):
    """
    actor 가 조회할 수 있는 User queryset.
    - division 이 주어지면: 해당 부서만 보기 적용 시 그 부서 소속만 (그리고 role_level 노출 규칙)
    - division 이 없으면: visible_divisions_for(actor) 안의 모든 사용자
    """
    if not actor.is_authenticated:
        return User.objects.none()
    divisions = visible_divisions_for(actor)
    if division is not None:
        if not can_see_division(actor, division):
            return User.objects.none()
        divisions = Division.objects.filter(pk=division.pk)
    # 해당 부서에 소속된 사용자 (division_teams 기준)
    return User.objects.filter(
        division_teams__division__in=divisions
    ).distinct()


def has_role_level_or_above(user: User, min_level_code: str) -> bool:
    """user 의 직급이 min_level_code 이상인지 (목사만 보기 → pastor, 전도사만 보기 → evangelist)."""
    if not user.is_authenticated or not user.role_level_id:
        return False
    try:
        min_level = RoleLevel.objects.get(code=min_level_code)
        return (user.role_level.level >= min_level.level)
    except RoleLevel.DoesNotExist:
        return False
