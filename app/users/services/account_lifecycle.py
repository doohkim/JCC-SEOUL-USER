"""계정 탈퇴(데이터 보존) — 신원 분리·비활성화."""

from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from retreat.models import RetreatAttendee, RetreatCouncilMembership, RetreatGroupMembership
from users.models import (
    PastoralDivisionAssignment,
    UserClub,
    UserDivisionTeam,
    UserFunctionalDeptRole,
    UserProfile,
)

User = get_user_model()

_KAKAO_USERNAME = re.compile(r"^kakao_(?P<uid>.+)$")


def _retired_username(user) -> str:
    """카카오 username 자리를 비워 재가입 시 신규 계정 생성 가능하게 한다."""
    match = _KAKAO_USERNAME.match(user.username or "")
    if match:
        uid = match.group("uid")
        return f"retired_{user.pk}_{uid}"[:150]
    return f"retired_{user.pk}_{user.username}"[:150]


@transaction.atomic
def retire_user(user, *, changed_by=None) -> None:
    """계정 탈퇴: User 행은 보존, 신원·연동만 분리.

    - 보존: RetreatAttendee(출석부), 주차·상담·변경이력 등 User FK CASCADE 대상
    - 연동 제거: RetreatGroupMembership, RetreatCouncilMembership, 소속/직책/동아리/목회담당
    - RetreatAttendee.user → NULL (조원 명단·출석 데이터 유지)
    """
    if user.is_superuser:
        raise ValueError("슈퍼유저 계정은 탈퇴 처리할 수 없습니다.")
    if getattr(user, "retired_at", None):
        return

    # 카카오 OAuth 연결 제거 → 동일 uid 재로그인 시 신규 User 생성
    user.social_auth.all().delete()

    # 수련회 조 조장/부조장·회장단 계정 연동 제거
    RetreatGroupMembership.objects.filter(user=user).delete()
    RetreatCouncilMembership.objects.filter(user=user).delete()

    # 조원 출석부: 행 유지, 계정 연동만 해제 (조장/부조장 역할은 일반 조원으로 강등)
    leader_roles = (
        RetreatAttendee.MemberRole.LEADER,
        RetreatAttendee.MemberRole.VICE_LEADER,
    )
    for attendee in RetreatAttendee.objects.filter(user=user):
        attendee.user = None
        if attendee.member_role in leader_roles:
            attendee.member_role = RetreatAttendee.MemberRole.MEMBER
            attendee.save(update_fields=["user", "member_role", "updated_at"])
        else:
            attendee.save(update_fields=["user", "updated_at"])

    # 앱 조직 소속·직책 연동 제거
    UserDivisionTeam.objects.filter(user=user).delete()
    UserFunctionalDeptRole.objects.filter(user=user).delete()
    UserClub.objects.filter(user=user).delete()
    PastoralDivisionAssignment.objects.filter(user=user).delete()

    # 프로필 고아화 (가입 신청 이력 보존)
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = None
    if profile is not None:
        profile.user = None
        profile.save(update_fields=["user", "updated_at"])

    user.username = _retired_username(user)
    user.is_active = False
    user.retired_at = timezone.now()
    user.save(update_fields=["username", "is_active", "retired_at"])
