"""
교적(Member) 부서·팀을 연결된 앱 계정(User)의 ``UserDivisionTeam`` 에 반영.

- Member에 ``linked_user`` 가 없으면 아무 것도 하지 않는다.
- 교적에 나타난 **부서별** 소속만 사용자 쪽에서 맞춘다(다른 부서에만 있는 User 전용 행은 건드리지 않음).
- 부서당 한 행이므로 Member 의 부서별 팀과 User 행을 맞추고, 같은 부서에서 빗나간 User 행은 삭제한다.
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
def sync_user_division_teams_from_member(
    member: Member,
    *,
    dropped_division_id: int | None = None,
) -> bool:
    """
    연결된 User 가 있으면 ``MemberDivisionTeam`` → ``UserDivisionTeam`` 동기화.

    ``dropped_division_id`` 는 ``MemberDivisionTeam`` 삭제 시그널에서 넘긴다. 교적에 다른 부서
    행이 남아 있을 때만, 삭제된 부서에 대한 User 행을 제거한다(교적 소속을 전부 지운 경우는
    기존처럼 User 를 비우지 않음).

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
            defaults={
                "team_id": r.team_id,
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

    # 교적에서 부서 행을 완전히 없앤 경우(다른 부서 행은 남음): 해당 부서 User 행만 제거.
    # 교적 소속이 전부 비면(m_rows 비움) User 쪽은 건드리지 않는다(문서·기존 동작).
    if dropped_division_id is not None and m_rows:
        if not MemberDivisionTeam.objects.filter(
            member_id=member.pk, division_id=dropped_division_id
        ).exists():
            UserDivisionTeam.objects.filter(
                user_id=user_id, division_id=dropped_division_id
            ).delete()

    logger.debug(
        "sync_user_division_teams_from_member member=%s user=%s rows=%s",
        member.pk,
        user_id,
        len(m_rows),
    )
    return True
