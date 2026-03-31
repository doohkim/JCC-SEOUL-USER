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

from .models import Division, RoleLevel, Team, User

_REGISTRY_ROLE_CODES = frozenset({"pastor", "evangelist"})
_ATTENDANCE_LEADER_ROLE_CODES = frozenset({"team_leader", "cell_leader"})
_ATTENDANCE_MANAGER_ROLE_CODES = frozenset({"attendance_admin"})
_PARKING_MANAGER_ROLE_CODES = frozenset({"parking_admin"})


def can_access_member_registry(user: User) -> bool:
    """교적(registry) Admin·조직 변경 API·멤버 쿼리 허용 여부."""
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    if user.is_staff:
        return True
    rl = getattr(user, "role_level", None)
    if rl is None:
        return False
    return getattr(rl, "code", None) in _REGISTRY_ROLE_CODES


def _functional_role_codes_for(user: User) -> set[str]:
    if not user.is_authenticated:
        return set()
    return set(user.functional_dept_roles.values_list("role__code", flat=True))


def is_platform_admin(user: User) -> bool:
    """전체 관리자(Django admin) 여부."""
    if not user.is_authenticated or not user.is_active:
        return False
    return bool(user.is_superuser or user.is_staff)


def _is_pastoral(user: User) -> bool:
    if not user.is_authenticated or not user.role_level_id:
        return False
    return getattr(user.role_level, "code", None) in _REGISTRY_ROLE_CODES


def _primary_user_division_ids(user: User) -> list[int]:
    primary = (
        user.division_teams.order_by("-is_primary", "sort_order", "division__sort_order", "id")
        .values_list("division_id", flat=True)
        .first()
    )
    if primary:
        return [int(primary)]
    first = user.division_teams.values_list("division_id", flat=True).first()
    return [int(first)] if first else []


def dashboard_divisions_for(user: User):
    """출석 대시보드에서 선택 가능한 부서 범위."""
    if not user.is_authenticated:
        return Division.objects.none()
    if is_platform_admin(user) or is_attendance_manager(user):
        return Division.objects.all()

    if _is_pastoral(user):
        pastoral_ids = list(
            user.pastoral_divisions.values_list("division_id", flat=True).distinct()
        )
        if pastoral_ids:
            return Division.objects.filter(pk__in=pastoral_ids)

    # 일반/팀장/셀장: 주 소속 1개만.
    primary_ids = _primary_user_division_ids(user)
    if primary_ids:
        return Division.objects.filter(pk__in=primary_ids)
    return Division.objects.none()


def is_attendance_manager(user: User) -> bool:
    """출석부 관리자(전체 인원 조회 허용) 여부."""
    if not user.is_authenticated or not user.is_active:
        return False
    role_codes = _functional_role_codes_for(user)
    return bool(role_codes & _ATTENDANCE_MANAGER_ROLE_CODES)


def can_access_attendance_roster(user: User) -> bool:
    """출석부(팀장 화면) 접근 허용 여부."""
    if not user.is_authenticated or not user.is_active:
        return False
    if is_platform_admin(user) or is_attendance_manager(user):
        return True
    role_codes = _functional_role_codes_for(user)
    return bool(role_codes & _ATTENDANCE_LEADER_ROLE_CODES)


def visible_divisions_for(user: User):
    """
    출석·대시보드 등 **부서 단위 운영 데이터** 조회 범위.
    소속 부서만 (전도사라도 타 부서 출석 API는 불가 — 교적은 별도 ``registry_divisions_for``).
    """
    if not user.is_authenticated:
        return Division.objects.none()
    return dashboard_divisions_for(user)


def can_change_dashboard_division(user: User) -> bool:
    if not user.is_authenticated:
        return False
    if is_platform_admin(user) or is_attendance_manager(user):
        return True
    if _is_pastoral(user):
        return dashboard_divisions_for(user).count() > 1
    return False


def registry_divisions_for(user: User):
    """교적 Member 가 필터링되는 상위 부서 범위."""
    if not user.is_authenticated:
        return Division.objects.none()
    if is_platform_admin(user) or can_access_member_registry(user):
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
    if is_platform_admin(user):
        return True
    return registry_divisions_for(user).filter(pk=division.pk).exists()


def pastoral_divisions_for(user: User):
    """목사/전도사/관리자용 계정 관리 페이지의 부서 범위."""
    if not user.is_authenticated:
        return Division.objects.none()
    if is_platform_admin(user):
        return Division.objects.all()

    role_code = getattr(getattr(user, "role_level", None), "code", None)
    if role_code == "pastor":
        pastoral_ids = list(
            user.pastoral_divisions.values_list("division_id", flat=True).distinct()
        )
        if pastoral_ids:
            return Division.objects.filter(pk__in=pastoral_ids)
        division_ids = user.division_teams.values_list("division_id", flat=True).distinct()
        return Division.objects.filter(pk__in=division_ids)

    if role_code == "evangelist":
        primary_ids = _primary_user_division_ids(user)
        if primary_ids:
            return Division.objects.filter(pk__in=primary_ids)
        division_ids = user.division_teams.values_list("division_id", flat=True).distinct()[:1]
        return Division.objects.filter(pk__in=division_ids)

    return Division.objects.none()


def can_manage_division_accounts(user: User) -> bool:
    return pastoral_divisions_for(user).exists()


def can_access_parking_tab(user: User) -> bool:
    if not user.is_authenticated or not user.is_active:
        return False
    return True


def is_parking_manager(user: User) -> bool:
    if not user.is_authenticated or not user.is_active:
        return False
    if is_platform_admin(user):
        return True
    role_codes = _functional_role_codes_for(user)
    return bool(role_codes & _PARKING_MANAGER_ROLE_CODES)


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


def membership_divisions_for(user: User):
    """
    부서 선택 기본 범위: 사용자 소속(UserDivisionTeam) 부서만.
    - 관리자/목사/전도사 포함 공통 규칙
    - 교적/출석의 별도 상위 권한 로직과 무관하게 "소속" 기준으로만 반환
    """
    if not user.is_authenticated:
        return Division.objects.none()
    division_ids = user.division_teams.values_list("division_id", flat=True).distinct()
    # 일부 계정은 UserDivisionTeam 연결이 없을 수 있다.
    # 이 경우 화면이 전부 비어 보이지 않도록 DB 전체를 fallback으로 사용한다.
    if not division_ids:
        return Division.objects.all().order_by("sort_order", "name")
    return Division.objects.filter(pk__in=division_ids).order_by("sort_order", "name")


def visible_teams_for(user: User, division: Division):
    """
    선택한 부서에서 볼 수 있는 팀 범위.
    - 관리자/목사/전도사: 해당 부서의 모든 팀
    - 그 외: 해당 부서 내 본인 소속 팀만
    """
    if not user.is_authenticated:
        return Team.objects.none()
    role_code = getattr(getattr(user, "role_level", None), "code", None)
    if is_platform_admin(user) or role_code in {"pastor", "evangelist"}:
        return Team.objects.filter(division=division).order_by("sort_order", "name")
    return Team.objects.filter(
        division=division,
        user_division_teams__user=user,
    ).distinct().order_by("sort_order", "name")


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


def can_access_counseling_tab(user: User) -> bool:
    """상담 메뉴·페이지 접근(로그인 사용자)."""
    if not user.is_authenticated or not user.is_active:
        return False
    return True


def can_access_counseling_manage_tab(user: User) -> bool:
    """상담 예약 관리(목사·전도사) 탭."""
    if not can_access_counseling_tab(user):
        return False
    if is_platform_admin(user):
        return True
    return _is_pastoral(user)


def counselors_queryset_for_applicant(actor: User):
    """
    상담 신청 시 선택 가능한 목사·전도사.
    - 운영자: 전체 목사·전도사
    - 그 외: 신청자 ``visible_divisions_for`` 와 부서가 겹치는 목사·전도사만
    """
    if not actor.is_authenticated:
        return User.objects.none()
    if is_platform_admin(actor):
        return User.objects.filter(
            role_level__code__in=_REGISTRY_ROLE_CODES,
            is_active=True,
        ).distinct()
    divisions = visible_divisions_for(actor)
    if not divisions.exists():
        return User.objects.none()
    return User.objects.filter(
        role_level__code__in=_REGISTRY_ROLE_CODES,
        division_teams__division__in=divisions,
        is_active=True,
    ).distinct()


def can_access_counseling_request_object(user: User, counseling_request) -> bool:
    """상담 신청 건: 신청자·상담사만 (관리자도 타인 건 API 조회 불가)."""
    if not user.is_authenticated:
        return False
    return user.pk == counseling_request.applicant_id or user.pk == counseling_request.counselor_id


class IsCounselingParticipant(BasePermission):
    """DRF: 상담 신청 객체의 신청자 또는 상담사."""

    message = "이 상담 신청을 볼 권한이 없습니다."

    def has_object_permission(self, request, view, obj):
        return can_access_counseling_request_object(request.user, obj)


class IsCounselingCounselor(BasePermission):
    """DRF: 해당 상담 신청의 상담사 본인."""

    message = "상담사만 수행할 수 있습니다."

    def has_object_permission(self, request, view, obj):
        u = request.user
        return bool(u and u.is_authenticated and u.pk == obj.counselor_id)
