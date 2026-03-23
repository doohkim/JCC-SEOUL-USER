"""
권한/노출

- **운영 데이터(출석·부서 목록 등)**: 로그인 사용자는 ``UserDivisionTeam`` 으로 연결된
  상위 부서(Division)만 조회 가능. 타 부서 데이터는 API/쿼리에서 차단.
- **교적(Member·registry Admin·조직 API)**: 목사·전도사만 (RoleLevel 코드 ``pastor`` /
  ``evangelist``, 또는 level ≥ 80). 그 외 직급은 교적 미노출.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from registry.models import Member

from .models import Division, RoleLevel, User

# 시드(seed_org_chart) 기준: 전도사=80, 목사=100, 부장=60 (교적 제외)
_REGISTRY_MIN_LEVEL = 80
_REGISTRY_ROLE_CODES = frozenset({"pastor", "evangelist"})


def can_access_member_registry(user: User) -> bool:
    """교적(registry) Admin·조직 변경 API·멤버 쿼리 허용 여부."""
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    rl = getattr(user, "role_level", None)
    if rl is None:
        return False
    if getattr(rl, "code", None) in _REGISTRY_ROLE_CODES:
        return True
    return (rl.level or 0) >= _REGISTRY_MIN_LEVEL


def visible_divisions_for(user: User):
    """
    출석·대시보드 등 **부서 단위 운영 데이터** 조회 범위.
    소속 부서만 (전도사라도 타 부서 출석 API는 불가 — 교적은 별도 ``registry_divisions_for``).
    """
    if not user.is_authenticated:
        return Division.objects.none()
    if user.is_superuser:
        return Division.objects.all()
    division_ids = user.division_teams.values_list("division_id", flat=True).distinct()
    return Division.objects.filter(pk__in=division_ids)


def registry_divisions_for(user: User):
    """교적 Member 가 필터링되는 상위 부서 범위."""
    if not user.is_authenticated:
        return Division.objects.none()
    if user.is_superuser or can_access_member_registry(user):
        return Division.objects.all()
    return Division.objects.none()


def can_see_division(user: User, division: Division) -> bool:
    """운영(출석 등) 맥락에서 해당 부서를 볼 수 있는지."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.division_teams.filter(division=division).exists()


def can_see_division_for_registry(user: User, division: Division) -> bool:
    """교적 맥락에서 해당 부서 회원을 다룰 수 있는지."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return registry_divisions_for(user).filter(pk=division.pk).exists()


def members_visible_to(actor: User, division: Division | None = None):
    """교적 멤버 쿼리셋 — 목사·전도사(+)만 비어 있지 않음."""
    if not actor.is_authenticated:
        return Member.objects.none()
    if not can_access_member_registry(actor):
        return Member.objects.none()
    divisions = registry_divisions_for(actor)
    if division is not None:
        if not divisions.filter(pk=division.pk).exists():
            return Member.objects.none()
        divisions = Division.objects.filter(pk=division.pk)
    return Member.objects.filter(
        division_teams__division__in=divisions,
        is_active=True,
    ).distinct()


def users_visible_to(actor: User, division: Division | None = None):
    """앱 사용자 — 소속 상위 부서만 (교적과 무관하게 부서 간 격리)."""
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


class IsPastoralRegistryStaff(BasePermission):
    """DRF: 교적·조직 변경 API — 목사·전도사(+) 전용."""

    message = "교적·조직 관리는 목사·전도사만 이용할 수 있습니다."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and can_access_member_registry(u))
