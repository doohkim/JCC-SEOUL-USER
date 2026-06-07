"""
권한/노출

- **운영 데이터(출석·부서 목록 등)**: 로그인 사용자는 ``UserDivisionTeam`` 으로 연결된
  상위 부서(Division)만 조회 가능. 타 부서 데이터는 API/쿼리에서 차단.
- **교적(Member·registry Admin·조직 API)**: ``can_access_member_registry`` — **직급이 목사·전도사인 계정만**
  (Django staff·기능권한만으로는 탭/API/페이지 불가). 슈퍼유저는 예외.
  부서 범위는 ``registry_divisions_for`` — **목회 담당 부서** (``PastoralDivisionAssignment``)만.
  담당이 없으면 빈 범위(화면에 안내 문구). **전체 부서** 조회는 ``is_superuser`` 만.
- **탭 출석부** (``can_access_team_roster_tab``): 팀장·셀장은 기능 직책 **또는** 직급(RoleLevel)
  ``team_leader`` / ``cell_leader`` — 본인 팀만. 목사·전도사·회장·부회장·총무 및 출석관리·운영은 부서 전체 팀.
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

    - 슈퍼유저: 전체
    - 목사·전도사: 목회 담당 부서
    - 활성 수련회 회장단: 본인 ``UserDivisionTeam`` 소속 부서
    """
    if not user.is_authenticated:
        return Division.objects.none()
    if user.is_superuser:
        qs = Division.objects.all()
    else:
        div_ids: set[int] = set()
        role_code = getattr(getattr(user, "role_level", None), "code", None)
        if role_code in ("pastor", "evangelist"):
            div_ids.update(
                _pastoral_assigned_divisions(user).values_list("pk", flat=True)
            )
        from retreat.models import RetreatCouncilMembership, RetreatEvent

        active_event_ids = list(
            RetreatEvent.objects.filter(is_active=True).values_list("id", flat=True)
        )
        if active_event_ids and RetreatCouncilMembership.objects.filter(
            user=user, event_id__in=active_event_ids
        ).exists():
            div_ids.update(
                user.division_teams.values_list("division_id", flat=True).distinct()
            )
        if not div_ids:
            return Division.objects.none()
        qs = Division.objects.filter(pk__in=div_ids)
    return _apply_region_filter(qs, region)


def can_access_onboarding_approvals(user: User) -> bool:
    """가입 승인 탭 — 슈퍼유저·목사·전도사·활성 수련회 회장단(소속 부서)."""
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return onboarding_approval_divisions_for(user).exists()


def can_manage_division_accounts(user: User) -> bool:
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    if getattr(user, "can_manage_accounts", False):
        return True
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
    if getattr(user, "can_manage_parking", False):
        return True
    role_codes = _functional_role_codes_for(user)
    return bool(role_codes & _PARKING_MANAGER_ROLE_CODES)


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
# 수련회(Retreat) 권한 — 평시 출석과 분리된 별도 체계.
# ---------------------------------------------------------------------------

# "조 운영진(staff)" 으로 인정할 직급(RoleLevel) / 직책(Role) 코드.
# - "회장·부회장·총무"는 직급(RoleLevel) 차원의 임원.
# - "부장·차장·간사"는 직책(Role) 차원의 부서 운영진.
# region/division 매칭은 별도로 확인한다.
_RETREAT_STAFF_ROLE_LEVEL_CODES = {"president", "vice_president", "secretary_general"}
_RETREAT_STAFF_FUNCTIONAL_ROLE_CODES = {"dept_head", "deputy_dept_head", "secretary"}
_RETREAT_PASTORAL_ROLE_LEVEL_CODES = {"pastor", "evangelist"}


def is_retreat_group_leader(user: User, group) -> bool:
    """해당 그룹의 조장/부조장 멤버십이 있으면 True."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if group is None:
        return False
    return group.memberships.filter(user=user).exists()


def can_access_retreat_tab(user: User) -> bool:
    """좌측/모바일 '수련회' 메뉴 노출 여부 (event 단위가 아닌 일반 가시 체크).

    - 슈퍼유저
    - 수련회 회장단(어떤 행사의 회장단이든 1개 이상)
    - 목사·전도사 (RoleLevel)
    - 조장/부조장(어떤 그룹이든 멤버십 1개 이상)
    - 그 외 staff(회장·부회장·총무 직급, 부장·차장·간사 직책) + region 연결
    """

    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    if user.retreat_council_memberships.exists():
        return True
    role_code = getattr(getattr(user, "role_level", None), "code", "")
    if role_code in _RETREAT_PASTORAL_ROLE_LEVEL_CODES:
        return True
    if user.retreat_group_memberships.exists():
        return True
    if _user_has_retreat_staff_role(user) and _user_region_ids_via_divisions(user):
        return True
    return False


def is_retreat_council(user: User, event) -> bool:
    """해당 행사의 회장단(임원·총무·부회장·회장)인지."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    if event is None:
        return False
    return user.retreat_council_memberships.filter(event=event).exists()


def can_add_retreat_group(user: User, event) -> bool:
    """조 생성 권한 — 슈퍼유저·해당 행사 회장단만 (목사·전도사·조장 제외)."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    if event is None:
        return False
    return is_retreat_council(user, event)


def can_manage_retreat_group_leaders(user: User, group) -> bool:
    """조 운영진(조장·부조장) 추가·수정·삭제 — 슈퍼유저·회장단·본인 조 운영진."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    if group is None:
        return False
    if is_retreat_council(user, group.event):
        return True
    return is_retreat_group_leader(user, group)


def can_manage_retreat_sessions(user: User, event) -> bool:
    """출석부(세션) 생성·수정·삭제 권한 — 회장단/슈퍼유저만."""
    return is_retreat_council(user, event)


def visible_retreat_sessions_for(user: User, event):
    """현재 사용자가 볼 수 있는 수련회 출석부 범위.

    - 슈퍼유저/회장단/목사·전도사: 진행중 + 마감 모두 조회.
    - 조장·부조장 및 그 외 수련회 탭 접근자: 진행중만 조회.
    """

    from retreat.models import RetreatSession  # 순환 의존 회피

    if not user or not getattr(user, "is_authenticated", False) or event is None:
        return RetreatSession.objects.none()

    base = RetreatSession.objects.filter(event=event)
    if user.is_superuser or is_retreat_council(user, event):
        return base

    role_code = getattr(getattr(user, "role_level", None), "code", "")
    if role_code in _RETREAT_PASTORAL_ROLE_LEVEL_CODES:
        return base

    return base.filter(status=RetreatSession.Status.ACTIVE)


def is_retreat_council_any(user: User) -> bool:
    """탭 노출용: 어떤 활성 행사의 회장단이든 1개 이상 가지는가."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return user.retreat_council_memberships.exists()


def _user_has_retreat_staff_role(user: User) -> bool:
    """직급/직책 화이트리스트 어디에라도 들어있는지."""
    role_code = getattr(getattr(user, "role_level", None), "code", None)
    if role_code in _RETREAT_STAFF_ROLE_LEVEL_CODES:
        return True
    if role_code in _RETREAT_PASTORAL_ROLE_LEVEL_CODES:
        return True
    return user.functional_dept_roles.filter(
        role__code__in=_RETREAT_STAFF_FUNCTIONAL_ROLE_CODES
    ).exists()


def _user_division_ids(user: User) -> set[int]:
    return set(user.division_teams.values_list("division_id", flat=True).distinct())


def _user_pastoral_division_ids(user: User) -> set[int]:
    return set(user.pastoral_divisions.values_list("division_id", flat=True).distinct())


def _user_region_ids_via_divisions(user: User) -> set[int]:
    """사용자 소속/담당 부서가 속한 region id 집합."""
    div_ids = _user_division_ids(user) | _user_pastoral_division_ids(user)
    if not div_ids:
        return set()
    return set(
        Division.objects.filter(pk__in=div_ids)
        .values_list("region_id", flat=True)
        .distinct()
    )


def is_retreat_staff(user: User, event) -> bool:
    """수련회 운영진 판정 (관리자 페이지 접근).

    - 슈퍼유저 / 회장단 / 목사·전도사: 무조건 staff (전체 보기 권한자).
    - (회장·부회장·총무 직급) / (부장·차장·간사 직책): 본인 region 연결 시.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    if event is not None and user.retreat_council_memberships.filter(event=event).exists():
        return True
    role_code = getattr(getattr(user, "role_level", None), "code", "")
    if role_code in _RETREAT_PASTORAL_ROLE_LEVEL_CODES:
        return True
    if not _user_has_retreat_staff_role(user):
        return False
    return bool(_user_region_ids_via_divisions(user))


def visible_retreat_groups_for(user: User, event):
    """현재 사용자가 볼 수 있는 RetreatGroup 쿼리셋.

    전체 보기 (행사 내 모든 조):
      - 슈퍼유저
      - 수련회 회장단(회장·부회장·총무·임원) — event 단위 등록
      - 목사·전도사 (RoleLevel)

    본인 소속만:
      - 그 외 staff(회장·부회장·총무 직급, 부장·차장·간사 직책):
        본인 region/division 의 그룹
      - 조장/부조장: 자신이 멤버십을 가진 그룹만
      - 그 외: 빈 쿼리셋
    """

    from retreat.models import RetreatGroup  # 순환 의존 회피

    if not user or not getattr(user, "is_authenticated", False) or event is None:
        return RetreatGroup.objects.none()

    base = RetreatGroup.objects.filter(event=event)

    # 전체 보기 권한
    if user.is_superuser:
        return base
    if user.retreat_council_memberships.filter(event=event).exists():
        return base
    role_code = getattr(getattr(user, "role_level", None), "code", "")
    if role_code in _RETREAT_PASTORAL_ROLE_LEVEL_CODES:
        return base

    leader_group_ids = set(
        user.retreat_group_memberships.filter(group__event=event).values_list(
            "group_id", flat=True
        )
    )

    if _user_has_retreat_staff_role(user):
        region_ids = _user_region_ids_via_divisions(user)
        # 목사·전도사는 division 단위 담당 → division 도 함께 화이트리스트
        division_ids = _user_division_ids(user) | _user_pastoral_division_ids(user)
        staff_qs = base.filter(region_id__in=region_ids)
        if division_ids:
            staff_qs = staff_qs.filter(division_id__in=division_ids)
        if leader_group_ids:
            return (staff_qs | base.filter(pk__in=leader_group_ids)).distinct()
        return staff_qs

    if leader_group_ids:
        return base.filter(pk__in=leader_group_ids)
    return base.none()


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
        if is_retreat_staff(user, group.event):
            # staff 는 본인 region/division 한정.
            div_ids = _user_division_ids(user) | _user_pastoral_division_ids(user)
            return (
                group.region_id in _user_region_ids_via_divisions(user)
                and (not div_ids or group.division_id in div_ids)
            )
        return False
