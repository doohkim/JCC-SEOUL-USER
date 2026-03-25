"""앱 사용자(User) 부서·팀 이동."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from users.models import Division, Team, UserDivisionTeam

User = get_user_model()


def _ensure_team_in_division(team: Team, division: Division) -> None:
    if team.division_id != division.id:
        raise ValidationError(
            {"team": f"팀「{team}」은(는) 부서「{division}」에 속하지 않습니다."},
            code="team_division_mismatch",
        )


def _set_single_primary_in_division(
    user: User, division: Division, primary: UserDivisionTeam
) -> None:
    for row in UserDivisionTeam.objects.filter(user=user, division=division):
        want = row.pk == primary.pk
        if row.is_primary != want:
            row.is_primary = want
            row.save(update_fields=["is_primary"])


@transaction.atomic
def change_team_within_division(
    user: User,
    division: Division,
    new_team: Team | None,
    *,
    membership: UserDivisionTeam | None = None,
    make_primary: bool = True,
) -> UserDivisionTeam:
    if new_team is not None:
        _ensure_team_in_division(new_team, division)

    qs = UserDivisionTeam.objects.filter(user=user, division=division)
    if membership is not None:
        if membership.user_id != user.id or membership.division_id != division.id:
            raise ValidationError(
                {"membership": "선택한 소속 행이 사용자·부서와 맞지 않습니다."},
                code="membership_mismatch",
            )
        udt = membership
    else:
        udt = qs.first()
        if udt is None:
            return UserDivisionTeam.objects.create(
                user=user,
                division=division,
                team=new_team,
                is_primary=True,
                sort_order=0,
            )

    udt.team = new_team
    if make_primary:
        udt.is_primary = True
    udt.save(update_fields=["team", "is_primary"])
    if make_primary:
        _set_single_primary_in_division(user, division, udt)
    return udt


@transaction.atomic
def transfer_to_division(
    user: User,
    *,
    from_division: Division | None,
    to_division: Division,
    team: Team | None,
    remove_from_source: bool = True,
    make_primary: bool = True,
) -> UserDivisionTeam:
    if team is not None:
        _ensure_team_in_division(team, to_division)

    if remove_from_source and from_division is not None:
        UserDivisionTeam.objects.filter(user=user, division=from_division).delete()

    udt, created = UserDivisionTeam.objects.get_or_create(
        user=user,
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
        if udt.team_id != tid:
            udt.team = team
            update_fields.append("team")
        if make_primary and not udt.is_primary:
            udt.is_primary = True
            update_fields.append("is_primary")
        if update_fields:
            udt.save(update_fields=update_fields)
    if make_primary:
        _set_single_primary_in_division(user, to_division, udt)
    return udt
