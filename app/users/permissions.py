"""
권한/노출

페이지·탭별 진입 함수 (UI ``permission_tags`` · 뷰 ``dispatch`` · DRF 와 동일하게 사용):

| 화면 | 함수 | 허용 조건 요약 |
|------|------|----------------|
| 출석 대시보드 ``/attendance/`` | ``can_access_attendance_dashboard`` | 슈퍼유저·목사/전도사·출석관리·탭출석부 권한·소속 1개 이상 |
| 탭 출석부 ``/attendance/team/roster/`` | ``can_access_team_roster_tab`` | 팀장/셀장(본인 팀) 또는 broad(출석관리·목사·임원·staff) |
| 출석 명단 입력 ``/attendance/roster/`` | ``can_access_attendance_roster_input`` | broad 출석 권한 (출석관리 플래그 포함) |
| 교적부 ``/registry/…`` | ``can_access_member_registry`` | 슈퍼유저·목사/전도사 직급만 |
| 계정관리 | ``can_manage_division_accounts`` | 슈퍼유저·``can_manage_accounts``·staff |
| 함께하기(공지) | ``can_access_notices_tab`` | 로그인 사용자 |
| 수련회 | ``can_access_retreat_tab`` | 회장단·목사/전도사·조장 등 (별도 체계) |

- **운영 데이터(출석·부서 목록 등)**: ``UserDivisionTeam`` 소속 부서만.
- **교적 부서 범위**: ``registry_divisions_for`` — 목회 담당 부서만.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from registry.models import Member

from .models import Division, Region, RoleLevel, Team, User


def _apply_region_filter(qs, region):
    """region 인자가 지정된 경우만 부서 쿼리셋을 해당 지역으로 좁힌다.

    - region 이 None 이면 변경 없음(기본 동작 = 기존과 동일).
    - Region 인스턴스/PK/code(slug) 어떤 형태로 들어와도 받는다.
    """

    if region is None:
        return qs
    if isinstance(region, Region):
        return qs.filter(region=region)
    if isinstance(region, int):
        return qs.filter(region_id=region)
    return qs.filter(region__code=str(region))

_REGISTRY_ROLE_CODES = frozenset({"pastor", "evangelist"})
_ATTENDANCE_LEADER_ROLE_CODES = frozenset({"team_leader", "cell_leader"})
_ATTENDANCE_MANAGER_ROLE_CODES = frozenset({"attendance_admin"})
# 탭 출석부: 부서 전체 팀 조회·입력 (직급 RoleLevel.code)
_TEAM_ROSTER_BROAD_ROLE_LEVEL_CODES = frozenset(
    {
        "pastor",
        "evangelist",
        "president",
        "vice_president",
        "secretary_general",
    }
)
_PARKING_MANAGER_ROLE_CODES = frozenset({"parking_admin"})
_ACCOUNT_MANAGER_ROLE_CODES = frozenset({"account_admin"})


def can_access_member_registry(user: User) -> bool:
    """교적(registry) Admin·조직 변경 API·멤버 쿼리·좌측 '교적부' 탭 허용 여부."""
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
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


def limits_registry_division_scope(user: User) -> bool:
    """
    교적·조직 API/Admin에서 부서·팀 선택지를 담당·소속으로 제한할지.
    목사·전도사(슈퍼유저 제외)만 True.
    """
    if not user.is_authenticated or user.is_superuser:
        return False
    return _is_pastoral(user)


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


def _divisions_from_udt(user: User):
    """소속(UserDivisionTeam) 부서만 (복수). 없으면 빈 쿼리셋."""
    division_ids = list(user.division_teams.values_list("division_id", flat=True).distinct())
    if not division_ids:
        return Division.objects.none()
    return Division.objects.filter(pk__in=division_ids).order_by(
        "region__sort_order", "sort_order", "name"
    )


def _pastoral_assigned_divisions(user: User):
    """
    목사·전도사 업무 부서: **목회 담당** (PastoralDivisionAssignment)만.
    미지정 시 빈 범위 — 소속(UDT)으로는 채우지 않음.
    """
    pastoral_ids = list(
        user.pastoral_divisions.values_list("division_id", flat=True).distinct()
    )
    if not pastoral_ids:
        return Division.objects.none()
    return Division.objects.filter(pk__in=pastoral_ids).order_by(
        "region__sort_order", "sort_order", "name"
    )


def dashboard_divisions_for(user: User, *, region=None):
    """출석 대시보드에서 선택 가능한 부서 범위. 전체 부서는 슈퍼유저만.

    region 인자(Region|int|code) 지정 시 해당 지역으로 추가 필터.
    """
    if not user.is_authenticated:
        return Division.objects.none()
    if user.is_superuser:
        qs = Division.objects.all()
    elif is_attendance_manager(user) or (user.is_staff and not user.is_superuser):
        qs = _divisions_from_udt(user)
    elif _is_pastoral(user):
        qs = _pastoral_assigned_divisions(user)
    else:
        # 일반/팀장/셀장: 주 소속 1개만.
        primary_ids = _primary_user_division_ids(user)
        qs = Division.objects.filter(pk__in=primary_ids) if primary_ids else Division.objects.none()
    return _apply_region_filter(qs, region)


def is_attendance_manager(user: User) -> bool:
    """출석부 관리자(전체 인원 조회 허용) 여부."""
    if not user.is_authenticated or not user.is_active:
        return False
    if getattr(user, "can_manage_attendance", False):
        return True
    role_codes = _functional_role_codes_for(user)
    return bool(role_codes & _ATTENDANCE_MANAGER_ROLE_CODES)


def is_team_roster_broad_access(user: User) -> bool:
    """
    탭 출석부에서 부서 **전체 팀**을 볼 수 있고 입력할 수 있는지.

    - Django 운영·출석 관리 플래그/직책
    - 직급: 목사·전도사·회장·부회장·총무 (RoleLevel.code)
    """

    if not user.is_authenticated or not user.is_active:
        return False
    if is_platform_admin(user) or is_attendance_manager(user):
        return True
    rl = getattr(user, "role_level", None)
    code = getattr(rl, "code", None) if rl is not None else None
    return code in _TEAM_ROSTER_BROAD_ROLE_LEVEL_CODES


def is_team_roster_leader_only(user: User) -> bool:
    """
    팀장·셀장 — broad 가 아닐 때 본인 팀만.

    인정: ``UserFunctionalDeptRole`` 의 역할 코드 **또는** ``User.role_level`` 직급 코드
    (운영에서 직급만 맞춰 두고 기능 직책 행을 안 쓴 경우가 많음).
    """

    if not user.is_authenticated or not user.is_active:
        return False
    if is_team_roster_broad_access(user):
        return False
    if _functional_role_codes_for(user) & _ATTENDANCE_LEADER_ROLE_CODES:
        return True
    rl = getattr(user, "role_level", None)
    code = getattr(rl, "code", None) if rl is not None else None
    return code in _ATTENDANCE_LEADER_ROLE_CODES


def can_access_team_roster_tab(user: User) -> bool:
    """좌측 '출석부' 탭·탭 출석부 API·HTML 접근 가능 여부."""

    if not user.is_authenticated or not user.is_active:
        return False
    return is_team_roster_broad_access(user) or is_team_roster_leader_only(user)


def can_access_attendance_roster(user: User) -> bool:
    """탭 출석부 접근 — ``can_access_team_roster_tab`` 과 동일."""

    return can_access_team_roster_tab(user)


def can_access_attendance_dashboard(user: User) -> bool:
    """출석 대시보드 ``/attendance/`` 페이지·탭."""
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser or _is_pastoral(user):
        return True
    if is_attendance_manager(user):
        return True
    if can_access_team_roster_tab(user):
        return True
    return bool(_primary_user_division_ids(user))


def can_access_attendance_roster_input(user: User) -> bool:
    """교적 연동 출석 명단 입력 ``/attendance/roster/`` (부서 전체 명단 편집)."""
    if not user.is_authenticated or not user.is_active:
        return False
    return is_team_roster_broad_access(user)


def visible_divisions_for(user: User, *, region=None):
    """
    출석·대시보드 등 **부서 단위 운영 데이터** 조회 범위.
    소속 부서만 (전도사라도 타 부서 출석 API는 불가 — 교적은 별도 ``registry_divisions_for``).
    region 인자 지정 시 해당 지역으로 추가 필터.
    """
    if not user.is_authenticated:
        return Division.objects.none()
    return dashboard_divisions_for(user, region=region)


def can_change_dashboard_division(user: User) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if is_attendance_manager(user):
        return dashboard_divisions_for(user).count() > 1
    if _is_pastoral(user):
        return dashboard_divisions_for(user).count() > 1
    return False


def registry_divisions_for(user: User, *, region=None):
    """
    교적 Member·조직 API·부서 드롭다운의 상위 부서 범위.

    - 슈퍼유저: 전체 부서
    - 목사·전도사: 목회 담당 부서만 (없으면 빈 쿼리셋)
    - 그 외: 접근 불가 (빈 쿼리셋)
    region 인자 지정 시 해당 지역으로 추가 필터.
    """
    if not user.is_authenticated:
        return Division.objects.none()
    if user.is_superuser:
        qs = Division.objects.all()
    elif not can_access_member_registry(user):
        return Division.objects.none()
    else:
        qs = _pastoral_assigned_divisions(user)
    return _apply_region_filter(qs, region)


def registry_scope_notice(user: User) -> str:
    """교적 화면/API: 담당 부서가 없을 때 안내 문구 (없으면 빈 문자열)."""
    if not user.is_authenticated or user.is_superuser:
        return ""
    if not can_access_member_registry(user):
        return ""
    if registry_divisions_for(user).exists():
        return ""
    return "담당 부서가 없어 교적을 조회할 수 없습니다. 관리자에게 목회 담당 부서 등록을 요청해 주세요."


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


def pastoral_divisions_for(user: User, *, region=None):
    """
    가입 승인·부서 계정 관리 등에서 쓰는 부서 범위.

    - 슈퍼유저: 전체 부서
    - 목사·전도사: 목회 담당 부서만 (없으면 빈 쿼리셋)
    - 그 외: 없음
    region 인자 지정 시 해당 지역으로 추가 필터.
    """
    if not user.is_authenticated:
        return Division.objects.none()
    if user.is_superuser:
        qs = Division.objects.all()
    else:
        role_code = getattr(getattr(user, "role_level", None), "code", None)
        if role_code in ("pastor", "evangelist"):
            qs = _pastoral_assigned_divisions(user)
        else:
            return Division.objects.none()
    return _apply_region_filter(qs, region)


def onboarding_approval_divisions_for(user: User, *, region=None):
    """
    가입 승인 탭에서 다룰 수 있는 부서.

    - 스태프(슈퍼유저·is_staff): 전체
    - 계정 관리 기능권한(can_manage_accounts): 본인 소속 부서만
    """
    if not user.is_authenticated:
        return Division.objects.none()
    if is_platform_admin(user):
        qs = Division.objects.all()
    elif getattr(user, "can_manage_accounts", False):
        qs = membership_divisions_for(user)
    else:
        return Division.objects.none()
    return _apply_region_filter(qs, region)


def can_access_onboarding_approvals(user: User) -> bool:
    """가입 승인 탭 — 스태프(슈퍼유저·is_staff) 또는 계정 관리 기능권한(소속 부서)."""
    if not user.is_authenticated or not user.is_active:
        return False
    if is_platform_admin(user):
        return True
    return onboarding_approval_divisions_for(user).exists()


def can_manage_division_accounts(user: User) -> bool:
    """부서 계정(통합 편집) 탭: 스태프(슈퍼유저·is_staff) 또는 can_manage_accounts 기능권한."""
    if not user.is_authenticated or not user.is_active:
        return False
    if is_platform_admin(user):
        return True
    return bool(getattr(user, "can_manage_accounts", False))


def can_access_parking_tab(user: User) -> bool:
    if not user.is_authenticated or not user.is_active:
        return False
    return True


def is_parking_manager(user: User) -> bool:
    if not user.is_authenticated or not user.is_active:
        return False
    if is_platform_admin(user):
        return True
    if getattr(user, "can_manage_parking", False):
        return True
    role_codes = _functional_role_codes_for(user)
    return bool(role_codes & _PARKING_MANAGER_ROLE_CODES)


def can_access_notices_tab(user: User) -> bool:
    """공지 열람 — 공지관리자/스태프/슈퍼유저 또는 가입신청 제출(승인대기·승인완료) 계정."""
    if not user.is_authenticated or not user.is_active:
        return False
    if is_notice_manager(user):
        return True
    from users.mixins import has_submitted_signup

    return has_submitted_signup(user)


def is_notice_manager(user: User) -> bool:
    """공지사항 작성·수정·삭제 권한.

    - 슈퍼유저·플랫폼 관리자(is_staff)
    - 공지 관리 기능권한(can_manage_notices)
    """
    if not user.is_authenticated or not user.is_active:
        return False
    if is_platform_admin(user):
        return True
    return bool(getattr(user, "can_manage_notices", False))


def can_access_pastoral_tab(user: User) -> bool:
    """@deprecated UI 호환 — 교적부 탭과 동일. 신규 코드는 ``can_access_member_registry`` 사용."""
    return can_access_member_registry(user)


def is_account_manager(user: User) -> bool:
    """계정 관리(부서 계정 직책 관리) 권한."""
    if not user.is_authenticated or not user.is_active:
        return False
    if is_platform_admin(user):
        return True
    if getattr(user, "can_manage_accounts", False):
        return True
    role_codes = _functional_role_codes_for(user)
    if role_codes & _ACCOUNT_MANAGER_ROLE_CODES:
        return True
    return pastoral_divisions_for(user).exists()


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


def membership_divisions_for(user: User, *, region=None):
    """
    부서 선택 기본 범위: 사용자 소속(UserDivisionTeam) 부서만.
    소속 행이 없으면 빈 목록(전체 부서 fallback 없음).
    region 인자 지정 시 해당 지역으로 추가 필터.
    """
    if not user.is_authenticated:
        return Division.objects.none()
    division_ids = user.division_teams.values_list("division_id", flat=True).distinct()
    if not division_ids:
        return Division.objects.none()
    qs = Division.objects.filter(pk__in=division_ids).order_by(
        "region__sort_order", "sort_order", "name"
    )
    return _apply_region_filter(qs, region)


def visible_teams_for(user: User, division: Division):
    """
    선택한 부서에서 볼 수 있는 팀 범위.
    - 슈퍼유저·목사·전도사: 해당 부서의 모든 팀
    - 그 외: 해당 부서 내 본인 소속 팀만
    """
    if not user.is_authenticated:
        return Team.objects.none()
    role_code = getattr(getattr(user, "role_level", None), "code", None)
    if user.is_superuser or role_code in {"pastor", "evangelist"}:
        return Team.objects.filter(division=division).order_by("sort_order", "name")
    return Team.objects.filter(
        division=division,
        user_division_teams__user=user,
    ).distinct().order_by("sort_order", "name")


def visible_regions_for(user: User):
    """사용자에게 노출 가능한 Region 목록.

    - 슈퍼유저: 전체
    - 그 외: 본인이 접근 가능한 Division 들이 속한 Region
    """
    if not user.is_authenticated:
        return Region.objects.none()
    if user.is_superuser:
        return Region.objects.all().order_by("sort_order", "name")
    division_qs = visible_divisions_for(user)
    region_ids = list(division_qs.values_list("region_id", flat=True).distinct())
    if not region_ids:
        return Region.objects.none()
    return Region.objects.filter(pk__in=region_ids).order_by("sort_order", "name")


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


class IsIntegrationService(BasePermission):
    """
    외부 서버 연동 — ``IntegrationServiceAuthentication`` 으로 발급된
    :class:`~users.models.ExternalServiceClient` 가 ``request.auth`` 에 있을 때만 허용.
    """

    message = "유효한 연동 서비스 키(X-JCC-Integration-Key)가 필요합니다."

    def has_permission(self, request, view):
        from .models import ExternalServiceClient

        return isinstance(getattr(request, "auth", None), ExternalServiceClient)


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


def pastors_queryset_for_applicant(actor: User):
    """
    상담 신청 시 선택 가능한 목사·전도사.
    - 운영자: 전체 목사·전도사
    - 그 외: 신청자 ``visible_divisions_for`` 와 부서가 겹치는 목사·전도사만
    """
    if not actor.is_authenticated:
        return User.objects.none()
    if actor.is_superuser:
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
    """상담 신청 건: 신청자·목회자만 (관리자도 타인 건 API 조회 불가)."""
    if not user.is_authenticated:
        return False
    return user.pk == counseling_request.applicant_id or user.pk == counseling_request.pastor_id


class IsCounselingParticipant(BasePermission):
    """DRF: 상담 신청 객체의 신청자 또는 목회자."""

    message = "이 상담 신청을 볼 권한이 없습니다."

    def has_object_permission(self, request, view, obj):
        return can_access_counseling_request_object(request.user, obj)


class IsCounselingPastor(BasePermission):
    """DRF: 해당 상담 신청의 목회자 본인."""

    message = "목회자만 수행할 수 있습니다."

    def has_object_permission(self, request, view, obj):
        u = request.user
        return bool(u and u.is_authenticated and u.pk == obj.pastor_id)


# ---------------------------------------------------------------------------
# 수련회(Retreat) 권한 — 평시 출석·조직 직급과 분리.
# 집회 운영진 = ``RetreatCouncilMembership`` 역할·범위. 정책은 staff_capabilities.
# ---------------------------------------------------------------------------

from retreat.services.staff_capabilities import (  # noqa: E402
    AccessLevel,
    effective_capabilities,
    get_staff_membership,
    staff_capabilities,
    visible_groups_qs,
)


def get_retreat_capabilities(user: User, event):
    """집회 단위 effective capability (운영진 ∪ 조장)."""
    return effective_capabilities(user, event)


def is_retreat_event_admin(user: User, event) -> bool:
    """집회 전체 관리자 또는 슈퍼유저."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    if event is None:
        return False
    from retreat.models import RetreatCouncilMembership

    return user.retreat_council_memberships.filter(
        event=event, role=RetreatCouncilMembership.Role.EVENT_ADMIN
    ).exists()


def is_retreat_group_leader(user: User, group) -> bool:
    """해당 그룹의 조장/부조장 멤버십이 있으면 True."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if group is None:
        return False
    return group.memberships.filter(user=user).exists()


def can_access_retreat_tab(user: User) -> bool:
    """좌측/모바일 '수련회' 메뉴 노출 여부.

    - 슈퍼유저
    - 집회 운영진(어떤 집회든 1건 이상)
    - 조장/부조장(어떤 그룹이든 멤버십 1개 이상)
    """

    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    if user.retreat_council_memberships.exists():
        return True
    if user.retreat_group_memberships.exists():
        return True
    return False


def is_retreat_council(user: User, event) -> bool:
    """하위 호환: 집회 전체 관리자(``event_admin``) 또는 슈퍼유저."""
    return is_retreat_event_admin(user, event)


def can_add_retreat_group(user: User, event) -> bool:
    """조 생성 권한."""
    if not user or not getattr(user, "is_authenticated", False) or event is None:
        return False
    return effective_capabilities(user, event).add_group


def can_manage_retreat_pickup(user: User, event) -> bool:
    """픽업 입회/출회 탭에서 추가·수정·삭제 가능 여부."""
    if not user or not getattr(user, "is_authenticated", False) or event is None:
        return False
    caps = effective_capabilities(user, event)
    return (
        caps.pickup_arrival >= AccessLevel.MUTATE
        or caps.pickup_departure >= AccessLevel.MUTATE
    )


def can_manage_retreat_pickup_location(user: User, event) -> bool:
    """탑승장소 목록 관리 — 집회 전체 관리자·슈퍼유저."""
    return is_retreat_event_admin(user, event)


def can_select_pickup_group(user: User, event) -> bool:
    """픽업 등록 시 조/지역/부서 직접 선택."""
    if not user or not getattr(user, "is_authenticated", False) or event is None:
        return False
    return effective_capabilities(user, event).pickup_select_group


def retreat_pickup_group_ids_for(user: User, event) -> set[int]:
    """조장/부조장으로서 본인이 속한(=관리하는) 조 id 집합.

    픽업 목록 필터·본인 조 자동 지정·삭제 권한 판단에 사용.
    """
    if not user or not getattr(user, "is_authenticated", False) or event is None:
        return set()
    return set(
        user.retreat_group_memberships.filter(group__event=event).values_list(
            "group_id", flat=True
        )
    )


def retreat_pickup_visible_group_ids_for(user: User, event) -> list[int]:
    """픽업 목록 조회 범위."""
    if not user or not getattr(user, "is_authenticated", False) or event is None:
        return []
    caps = effective_capabilities(user, event)
    if caps.pickup_select_group and caps.scope.kind == "event":
        from retreat.models import RetreatGroup

        return list(
            RetreatGroup.objects.filter(event=event).values_list("id", flat=True)
        )
    return list(visible_groups_qs(user, event).values_list("id", flat=True))


def is_retreat_pastoral_observer(user: User, event) -> bool:
    """[deprecated] 목사·전도사 수련회 권한 제거 — 항상 False."""
    return False


def can_manage_retreat_group_leaders(user: User, group) -> bool:
    """조 운영진(조장·부조장) 추가·수정·삭제."""
    if not user or not getattr(user, "is_authenticated", False) or group is None:
        return False
    caps = effective_capabilities(user, group.event)
    if caps.edit_group:
        return True
    return is_retreat_group_leader(user, group)


def can_manage_retreat_sessions(user: User, event) -> bool:
    """출석부(세션) 생성·수정·삭제 — 집회 전체 관리자·슈퍼유저."""
    return is_retreat_event_admin(user, event)


def visible_retreat_sessions_for(user: User, event):
    """현재 사용자가 볼 수 있는 수련회 출석부 범위."""

    from retreat.models import RetreatSession  # 순환 의존 회피

    if not user or not getattr(user, "is_authenticated", False) or event is None:
        return RetreatSession.objects.none()

    base = RetreatSession.objects.filter(event=event)
    caps = effective_capabilities(user, event)
    if user.is_superuser or caps.manage_timetable or is_retreat_event_admin(user, event):
        return base
    if caps.view_changelog or caps.admin >= AccessLevel.VIEW:
        return base
    return base.filter(status=RetreatSession.Status.ACTIVE)


def is_retreat_council_any(user: User) -> bool:
    """탭 노출용: 어떤 활성 집회의 운영진이든 1개 이상."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return user.retreat_council_memberships.exists()


def is_retreat_staff(user: User, event) -> bool:
    """관리 탭·변경 이력 등 — admin 탭 VIEW 이상."""
    if not user or not getattr(user, "is_authenticated", False) or event is None:
        return False
    if user.is_superuser:
        return True
    return effective_capabilities(user, event).admin >= AccessLevel.VIEW


def can_view_retreat_all(user: User, event) -> bool:
    """숙소 탭·집회 전체 숙소 데이터 — lodging VIEW + event scope."""
    if not user or not getattr(user, "is_authenticated", False) or event is None:
        return False
    caps = effective_capabilities(user, event)
    return caps.lodging >= AccessLevel.VIEW and caps.scope.kind == "event"


def can_change_retreat_check_in(user: User, event) -> bool:
    """입·퇴실 상태 변경."""
    if not user or not getattr(user, "is_authenticated", False) or event is None:
        return False
    return effective_capabilities(user, event).change_check_in


def can_link_attendee_user(user: User, event) -> bool:
    """조원 사용자 계정 연동."""
    if not user or not getattr(user, "is_authenticated", False) or event is None:
        return False
    return effective_capabilities(user, event).link_attendee_user


def can_manage_staff(user: User, event) -> bool:
    """집회 운영진 명단 등록·수정·삭제."""
    if not user or not getattr(user, "is_authenticated", False) or event is None:
        return False
    return effective_capabilities(user, event).manage_staff


def can_view_staff(user: User, event) -> bool:
    """집회 운영진 명단 조회."""
    if not user or not getattr(user, "is_authenticated", False) or event is None:
        return False
    return effective_capabilities(user, event).view_staff


def can_delete_checked_out_attendee(user: User, event) -> bool:
    """퇴실 상태 조원 삭제 — 슈퍼유저만."""
    if not user or not getattr(user, "is_authenticated", False) or event is None:
        return False
    return effective_capabilities(user, event).delete_checked_out_attendee


def visible_retreat_groups_for(user: User, event):
    """현재 사용자가 볼 수 있는 RetreatGroup 쿼리셋."""
    return visible_groups_qs(user, event)


class IsRetreatGroupLeaderOrStaff(BasePermission):
    """DRF: 조 단위 객체에서 leader/vice_leader 또는 staff 권한."""

    message = "수련회 조 정보를 볼 권한이 없습니다."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        # obj 가 RetreatGroup 자체 또는 그룹 FK 를 가진 모델일 수 있다.
        group = obj if hasattr(obj, "memberships") and hasattr(obj, "event") else getattr(obj, "group", None)
        if group is None:
            return False
        user = request.user
        if user.is_superuser:
            return True
        if is_retreat_group_leader(user, group):
            return True
        visible_ids = set(
            visible_retreat_groups_for(user, group.event).values_list("id", flat=True)
        )
        return group.id in visible_ids
