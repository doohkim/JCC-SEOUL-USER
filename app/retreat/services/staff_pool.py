"""집회 운영진 등록 — 조(그룹)에 배정된 지역·부서 소속 사용자 풀."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from retreat.models import (
    RetreatCouncilMembership,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatGroupScope,
)
from users.models import UserProfile

User = get_user_model()


def event_staff_eligible_division_ids(event_id: int) -> set[int]:
    """집회 조·보조 범위에 연결된 부서 ID 집합."""
    division_ids = set(
        RetreatGroup.objects.filter(event_id=event_id).values_list(
            "division_id", flat=True
        )
    )
    division_ids.update(
        RetreatGroupScope.objects.filter(group__event_id=event_id).values_list(
            "division_id", flat=True
        )
    )
    return {d for d in division_ids if d}


def event_staff_assigned_user_ids(event_id: int) -> set[int]:
    council_ids = set(
        RetreatCouncilMembership.objects.filter(event_id=event_id).values_list(
            "user_id", flat=True
        )
    )
    group_ids = set(
        RetreatGroupMembership.objects.filter(group__event_id=event_id).values_list(
            "user_id", flat=True
        )
    )
    return council_ids | group_ids


def staff_pool_users_for_event(event_id: int) -> QuerySet:
    """탈퇴·미승인 제외, 집회 조 부서 소속(주 소속) 사용자. 이미 배정된 사람 제외."""
    division_ids = event_staff_eligible_division_ids(event_id)
    if not division_ids:
        return User.objects.none()

    qs = (
        User.objects.filter(
            is_active=True,
            retired_at__isnull=True,
            profile__onboarding_status=UserProfile.OnboardingStatus.APPROVED,
            division_teams__division_id__in=division_ids,
            division_teams__is_primary=True,
        )
        .select_related("profile")
        .distinct()
    )
    assigned = event_staff_assigned_user_ids(event_id)
    if assigned:
        qs = qs.exclude(id__in=assigned)
    return qs
