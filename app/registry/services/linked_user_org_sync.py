"""
교적(Member) 부서·팀을 연결된 앱 계정(User)의 ``UserDivisionTeam`` 에 반영.

- Member에 ``linked_user`` 가 없으면 아무 것도 하지 않는다.
- 교적에 나타난 **부서별** 소속만 사용자 쪽에서 맞춘다(다른 부서에만 있는 User 전용 행은 건드리지 않음).
- 해당 부서 안에서는 Member 의 (division, team) 집합과 User 행을 일치시키고, 빠진 조합은 삭제한다.
- 교적에 부서·팀 행이 **하나도 없을 때**는 User 쪽을 비우지 않는다(목사 등 Member만 두고
  ``UserDivisionTeam`` 으로 권한을 쓰는 경우를 지키기 위함). 전부 비운 뒤 앱 소속까지
  맞추려면 관리자에서 User 소속을 직접 정리하거나, 이후 전용 플래그/명령을 추가한다.
"""

from __future__ import annotations

import logging

from django.db import transaction

from registry.models import Member, MemberDivisionTeam
from users.models import UserDivisionTeam

logger = logging.getLogger("registry.linked_user_org_sync")


@transaction.atomic
def sync_user_division_teams_from_member(member: Member) -> bool:
    """
    연결된 User 가 있으면 ``MemberDivisionTeam`` → ``UserDivisionTeam`` 동기화.

    Returns:
        True if a linked user existed and sync ran, False if no linked user.
    """
    user_id = getattr(member, "linked_user_id", None)
    if not user_id:
        return False

    m_rows = list(
        MemberDivisionTeam.objects.filter(member_id=member.pk).select_related(
            "division", "team"
        )
    )
    member_keys = {(r.division_id, r.team_id) for r in m_rows}
    division_ids = {r.division_id for r in m_rows}

    for r in m_rows:
        UserDivisionTeam.objects.update_or_create(
            user_id=user_id,
            division_id=r.division_id,
            team_id=r.team_id,
            defaults={
                "is_primary": r.is_primary,
                "sort_order": r.sort_order,
            },
        )

    if division_ids:
        stale_ids = []
        for udt in UserDivisionTeam.objects.filter(
            user_id=user_id, division_id__in=division_ids
        ).only("id", "division_id", "team_id"):
            if (udt.division_id, udt.team_id) not in member_keys:
                stale_ids.append(udt.pk)
        if stale_ids:
            UserDivisionTeam.objects.filter(pk__in=stale_ids).delete()

    logger.debug(
        "sync_user_division_teams_from_member member=%s user=%s rows=%s",
        member.pk,
        user_id,
        len(m_rows),
    )
    return True
