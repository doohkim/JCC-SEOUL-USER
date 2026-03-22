"""Admin 인덱스 — ``registry`` (교적부)."""

from __future__ import annotations

REGISTRY_MODEL_GROUPS: dict[str, tuple[int, str, str]] = {
    "Member": (10, "교적 · 멤버 카드", "교적"),
    "MemberProfile": (15, "교적 · 프로필 상세", "교적"),
    "MemberDivisionTeam": (20, "교적 · 부서·팀·동아리 소속", "교적·조직"),
    "MemberClub": (20, "교적 · 부서·팀·동아리 소속", "교적·조직"),
    "MemberFunctionalDeptRole": (20, "교적 · 부서·팀·동아리 소속", "교적·조직"),
    "MemberFamilyMember": (30, "교적 · 가족·심방", "교적·기록"),
    "MemberVisitLog": (30, "교적 · 가족·심방", "교적·기록"),
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


def group_registry_models_for_template(models: list[dict]) -> list[dict]:
    annotated = _annotate(models, REGISTRY_MODEL_GROUPS)
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
