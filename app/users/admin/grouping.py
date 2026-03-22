"""
Admin 인덱스에서 ``users`` 앱 모델을 성격별로 묶기 위한 메타데이터.

``object_name`` 은 Django ``Model._meta.object_name`` (클래스명, 예: User).
"""

from __future__ import annotations

# (정렬 순서, 섹션 제목, 짧은 태그)
USERS_MODEL_GROUPS: dict[str, tuple[int, str, str]] = {
    # 계정·권한
    "User": (10, "계정 · 앱 로그인", "계정"),
    "RoleLevel": (10, "계정 · 앱 로그인", "계정"),
    "Role": (10, "계정 · 앱 로그인", "계정"),
    # 조직 마스터
    "Division": (20, "조직 · 부서·팀 등 기본 데이터", "조직"),
    "Team": (20, "조직 · 부서·팀 등 기본 데이터", "조직"),
    "Club": (20, "조직 · 부서·팀 등 기본 데이터", "조직"),
    "FunctionalDepartment": (20, "조직 · 부서·팀 등 기본 데이터", "조직"),
    # 앱 사용자 ↔ 조직
    "UserDivisionTeam": (30, "앱 사용자 · 부서·팀 소속", "앱·조직"),
    "UserClub": (30, "앱 사용자 · 부서·팀 소속", "앱·조직"),
    "UserFunctionalDeptRole": (30, "앱 사용자 · 부서·팀 소속", "앱·조직"),
    # 교적 본체
    "Member": (40, "교적 · 멤버 카드", "교적"),
    # 교적 ↔ 조직
    "MemberDivisionTeam": (50, "교적 · 부서·팀·동아리 소속", "교적·조직"),
    "MemberClub": (50, "교적 · 부서·팀·동아리 소속", "교적·조직"),
    "MemberFunctionalDeptRole": (50, "교적 · 부서·팀·동아리 소속", "교적·조직"),
    # 교적 부가
    "MemberFamilyMember": (60, "교적 · 가족·심방", "교적·기록"),
    "MemberVisitLog": (60, "교적 · 가족·심방", "교적·기록"),
    # 예배 명단
    "WorshipRosterScope": (70, "예배 명단 · 엑셀/스냅샷 구분", "명단"),
    "WorshipRosterEntry": (70, "예배 명단 · 엑셀/스냅샷 구분", "명단"),
    # 주간 출석
    "AttendanceWeek": (80, "주간 출석부 · 주차·수토·주일", "주간출석"),
    "MidweekAttendanceRecord": (80, "주간 출석부 · 주차·수토·주일", "주간출석"),
    "SundayAttendanceLine": (80, "주간 출석부 · 주차·수토·주일", "주간출석"),
    # 팀 출석 (교시 칩)
    "TeamAttendanceSession": (90, "팀 출석부 · 교시별 칩", "팀출석"),
    "TeamMemberSlotAttendance": (90, "팀 출석부 · 교시별 칩", "팀출석"),
}


def annotate_users_admin_models(models: list[dict]) -> list[dict]:
    """각 model dict 에 ``admin_group_*`` 키를 붙이고 정렬."""
    out = []
    for m in models:
        m = dict(m)
        on = m.get("object_name") or ""
        order, section, tag = USERS_MODEL_GROUPS.get(
            on,
            (999, "기타", "기타"),
        )
        m["admin_group_order"] = order
        m["admin_group_section"] = section
        m["admin_group_tag"] = tag
        out.append(m)
    out.sort(key=lambda x: (x["admin_group_order"], x.get("name") or ""))
    return out


def group_users_models_for_template(models: list[dict]) -> list[dict]:
    """
    템플릿용: ``{"section", "tag", "models": [...]}`` 리스트.

    같은 섹션끼리 묶어서 순서 유지.
    """
    annotated = annotate_users_admin_models(models)
    buckets: list[dict] = []
    key_to_idx: dict[tuple[int, str], int] = {}
    for m in annotated:
        k = (m["admin_group_order"], m["admin_group_section"])
        if k not in key_to_idx:
            key_to_idx[k] = len(buckets)
            buckets.append(
                {
                    "order": m["admin_group_order"],
                    "section": m["admin_group_section"],
                    "tag": m["admin_group_tag"],
                    "models": [],
                }
            )
        buckets[key_to_idx[k]]["models"].append(m)
    return buckets
