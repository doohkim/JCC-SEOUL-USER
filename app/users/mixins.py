from __future__ import annotations

from urllib.parse import urlencode

from django.contrib.auth.mixins import UserPassesTestMixin
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
    # 목사·전도사: 관리자가 직급만 부여한 계정은 소속·가입 승인 절차 없이도 교적 등 업무 화면을 써야 함.
    # (그렇지 않으면 OnboardingRequiredMixin 에 교적부가 막혀 "전도사인데 교적이 안 보인다"가 됨.)
    role_code = getattr(getattr(user, "role_level", None), "code", None)
    if role_code in ("pastor", "evangelist"):
        return True
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


def has_submitted_signup(user, profile: UserProfile | None = None) -> bool:
    """가입신청을 제출한 사용자 — 공지·타임테이블 등 열람 전용 페이지."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role_code = getattr(getattr(user, "role_level", None), "code", None)
    if role_code in ("pastor", "evangelist"):
        return True
    profile = profile or ensure_user_profile(user)
    status = profile.onboarding_status
    if status == UserProfile.OnboardingStatus.APPROVED:
        return True
    return status == UserProfile.OnboardingStatus.PENDING and bool(
        profile.requested_division_id
    )


class SignupSubmittedRequiredMixin:
    """승인대기(신청서 제출) + 승인완료 사용자만 통과. 반려·미신청은 온보딩으로."""

    onboarding_url = reverse_lazy("user_onboarding")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not has_submitted_signup(request.user):
            next_qs = urlencode({"next": request.get_full_path()})
            return HttpResponseRedirect(f"{self.onboarding_url}?{next_qs}")
        return super().dispatch(request, *args, **kwargs)


class SuperuserRequiredMixin(UserPassesTestMixin):
    """superuser 전용 (공지 작성·수정·삭제 등)."""

    def test_func(self):
        return bool(self.request.user.is_authenticated and self.request.user.is_superuser)


class OnboardingRequiredMixin:
    onboarding_url = reverse_lazy("user_onboarding")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_superuser:
            profile = ensure_user_profile(request.user)
            if not is_onboarding_complete(request.user, profile):
                next_qs = urlencode({"next": request.get_full_path()})
                return HttpResponseRedirect(f"{self.onboarding_url}?{next_qs}")
        return super().dispatch(request, *args, **kwargs)
