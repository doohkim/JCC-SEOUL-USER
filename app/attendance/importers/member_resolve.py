"""출석 임포트 공통: 주차·멤버 매칭·팀 해석."""

from __future__ import annotations

import re
from datetime import date, timedelta

from registry.importers.youth_roster_xlsx import TEAM_SLUG, ascii_username_base
from registry.models import Member
from users.models import Division, Team


def week_sunday_on_or_before(d: date) -> date:
    delta = (d.weekday() + 1) % 7
    return d - timedelta(days=delta)


def member_name_key(name: str) -> str:
    s = re.sub(r"\s*(팀장|셀장|부장|회장)\s*$", "", (name or "").strip())
    return re.sub(r"\s+", "", s)


def find_member(display_name: str, team: Team | None) -> Member | None:
    key = member_name_key(display_name)
    if not key or len(key) < 2:
        return None
    qs = Member.objects.filter(is_active=True)
    if team is not None:
        in_team = qs.filter(
            division_teams__team_id=team.id,
            division_teams__division_id=team.division_id,
        ).distinct()
        for m in in_team:
            if member_name_key(m.name) == key:
                return m
            if m.name_alias and member_name_key(m.name_alias) == key:
                return m
    for m in qs:
        if member_name_key(m.name) == key:
            return m
        if m.name_alias and member_name_key(m.name_alias) == key:
            return m
    return None


def allocate_import_key(display_name: str, used_ik: set[str]) -> str:
    base = (ascii_username_base(display_name) or "member")[:50]
    ik = base
    n = 1
    while ik in used_ik:
        ik = f"{base}_{n}"[:64]
        n += 1
    used_ik.add(ik)
    return ik


def resolve_team(team_header: str, division: Division) -> Team | None:
    t = team_header.replace(" ", "").strip()
    if "회장단" in t and "팀" not in t:
        existing = Team.objects.filter(division=division, name__icontains="회장단").first()
        if existing:
            return existing
        team, _ = Team.objects.get_or_create(
            division=division,
            code="hoejangdan",
            defaults={"name": "회장단", "sort_order": 0},
        )
        return team
    slug = TEAM_SLUG.get(t)
    if not slug:
        return None
    return Team.objects.filter(division=division, code=slug).first()
