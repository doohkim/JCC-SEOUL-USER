from __future__ import annotations

from urllib.parse import urlencode

from django.http import HttpResponseRedirect
from django.urls import reverse_lazy

from users.models import UserDivisionTeam, UserProfile


def ensure_user_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def is_onboarding_complete(user, profile: UserProfile | None = None) -> bool:
    if not user.is_authenticated or user.is_superuser:
        return True
    profile = profile or ensure_user_profile(user)
    has_membership = user.division_teams.exists()

    # 승인 상태인데 소속 행이 없으면 신청값 기준으로 1회 자동 보정.
    if (
        not has_membership
        and profile.onboarding_status == UserProfile.OnboardingStatus.APPROVED
        and profile.requested_division_id
    ):
        req_team = profile.requested_team
        if req_team and req_team.division_id != profile.requested_division_id:
            req_team = None
        UserDivisionTeam.objects.get_or_create(
            user=user,
            division=profile.requested_division,
            defaults={"team": req_team, "is_primary": True, "sort_order": 0},
        )
        has_membership = user.division_teams.exists()

    # 기존 계정(이미 소속 있음)은 승인 완료로 자동 보정.
    if has_membership and profile.onboarding_status != UserProfile.OnboardingStatus.APPROVED:
        profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
        profile.save(update_fields=["onboarding_status", "updated_at"])
    return has_membership and profile.onboarding_status == UserProfile.OnboardingStatus.APPROVED


class OnboardingRequiredMixin:
    onboarding_url = reverse_lazy("user_onboarding")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_superuser:
            profile = ensure_user_profile(request.user)
            if not is_onboarding_complete(request.user, profile):
                next_qs = urlencode({"next": request.get_full_path()})
                return HttpResponseRedirect(f"{self.onboarding_url}?{next_qs}")
        return super().dispatch(request, *args, **kwargs)
