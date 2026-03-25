"""교적(Member) 부서·팀 이동."""

from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.db import transaction

from registry.models import Member, MemberDivisionTeam
from users.models import Division, Team

logger = logging.getLogger("registry.org.member")


def _ensure_team_in_division(team: Team, division: Division) -> None:
    if team.division_id != division.id:
        raise ValidationError(
            {"team": f"팀「{team}」은(는) 부서「{division}」에 속하지 않습니다."},
            code="team_division_mismatch",
        )


def _set_single_primary_in_division(
    member: Member, division: Division, primary: MemberDivisionTeam
) -> None:
    for row in MemberDivisionTeam.objects.filter(member=member, division=division):
        want = row.pk == primary.pk
        if row.is_primary != want:
            row.is_primary = want
            row.save(update_fields=["is_primary"])


@transaction.atomic
def change_team_within_division(
    member: Member,
    division: Division,
    new_team: Team | None,
    *,
    membership: MemberDivisionTeam | None = None,
    make_primary: bool = True,
) -> MemberDivisionTeam:
    if new_team is not None:
        _ensure_team_in_division(new_team, division)

    qs = MemberDivisionTeam.objects.filter(member=member, division=division)
    if membership is not None:
        if membership.member_id != member.id or membership.division_id != division.id:
            raise ValidationError(
                {"membership": "선택한 소속 행이 멤버·부서와 맞지 않습니다."},
                code="membership_mismatch",
            )
        mdt = membership
    else:
        mdt = qs.first()
        if mdt is None:
            mdt = MemberDivisionTeam.objects.create(
                member=member,
                division=division,
                team=new_team,
                is_primary=True,
                sort_order=0,
            )
            return mdt

    mdt.team = new_team
    if make_primary:
        mdt.is_primary = True
    mdt.save(update_fields=["team", "is_primary"])
    if make_primary:
        _set_single_primary_in_division(member, division, mdt)
    return mdt


@transaction.atomic
def transfer_to_division(
    member: Member,
    *,
    from_division: Division | None,
    to_division: Division,
    team: Team | None,
    remove_from_source: bool = True,
    make_primary: bool = True,
) -> MemberDivisionTeam:
    if team is not None:
        _ensure_team_in_division(team, to_division)

    if remove_from_source and from_division is not None:
        MemberDivisionTeam.objects.filter(member=member, division=from_division).delete()

    mdt, created = MemberDivisionTeam.objects.get_or_create(
        member=member,
        division=to_division,
        defaults={
            "team": team,
            "is_primary": make_primary,
            "sort_order": 0,
        },
    )
    if not created:
        update_fields = []
        tid = team.id if team else None
        if mdt.team_id != tid:
            mdt.team = team
            update_fields.append("team")
        if make_primary and not mdt.is_primary:
            mdt.is_primary = True
            update_fields.append("is_primary")
        if update_fields:
            mdt.save(update_fields=update_fields)
    if make_primary:
        _set_single_primary_in_division(member, to_division, mdt)
    return mdt
