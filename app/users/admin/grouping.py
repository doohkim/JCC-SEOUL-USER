"""Admin 인덱스 — ``users`` 앱(계정·조직 마스터·앱 사용자 소속)."""

from __future__ import annotations

USERS_MODEL_GROUPS: dict[str, tuple[int, str, str]] = {
    "UserProfile": (12, "계정 · 프로필", "계정"),
    "User": (10, "계정 · 앱 로그인", "계정"),
    "RoleLevel": (10, "계정 · 앱 로그인", "계정"),
    "Role": (10, "계정 · 앱 로그인", "계정"),
    "Division": (20, "조직 · 부서·팀 등 기본 데이터", "조직"),
    "Team": (20, "조직 · 부서·팀 등 기본 데이터", "조직"),
    "Club": (20, "조직 · 부서·팀 등 기본 데이터", "조직"),
    "FunctionalDepartment": (20, "조직 · 부서·팀 등 기본 데이터", "조직"),
    "UserDivisionTeam": (30, "앱 사용자 · 부서·팀 소속", "앱·조직"),
    "UserClub": (30, "앱 사용자 · 부서·팀 소속", "앱·조직"),
    "UserFunctionalDeptRole": (30, "앱 사용자 · 부서·팀 소속", "앱·조직"),
}


def _annotate(models: list[dict], mapping: dict) -> list[dict]:
    out = []
    for m in models:
        m = dict(m)
        on = m.get("object_name") or ""
        order, section, tag = mapping.get(on, (999, "기타", "기타"))
        m["admin_group_order"] = order
        m["admin_group_section"] = section
        m["admin_group_tag"] = tag
        out.append(m)
    out.sort(key=lambda x: (x["admin_group_order"], x.get("name") or ""))
    return out


def group_users_models_for_template(models: list[dict]) -> list[dict]:
    annotated = _annotate(models, USERS_MODEL_GROUPS)
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
