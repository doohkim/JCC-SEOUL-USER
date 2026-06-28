"""가입 승인 시 목회자 계정(role_level·목회 담당 부서) 자동 반영."""

from __future__ import annotations

from retreat.services.onboarding import is_pastoral_applicant
from users.models import PastoralDivisionAssignment, RoleLevel, UserProfile


def apply_pastoral_account_setup(user, profile) -> None:
    """목사/전도사 가입 신청 승인 시 User.role_level·PastoralDivisionAssignment 설정."""
    if user is None or profile is None or not is_pastoral_applicant(profile):
        return

    role_code = profile.requested_applicant_role
    role_level = RoleLevel.objects.filter(code=role_code).first()
    if role_level is not None and user.role_level_id != role_level.id:
        user.role_level = role_level
        user.save(update_fields=["role_level"])

    if profile.requested_division_id:
        PastoralDivisionAssignment.objects.get_or_create(
            user=user,
            division_id=profile.requested_division_id,
            defaults={"is_primary": True, "sort_order": 0},
        )


def signup_application_detail(profile) -> dict:
    """계정 탭 팝업용 가입 신청서 읽기 전용 요약."""
    if profile is None or not profile.requested_division_id:
        return {"has_application": False}

    div = profile.requested_division
    region_name = ""
    if div and div.region_id:
        region_name = getattr(div.region, "name", "") or ""

    applicant_role = profile.requested_applicant_role or UserProfile.ApplicantRole.MEMBER
    applicant_role_label = dict(UserProfile.ApplicantRole.choices).get(
        applicant_role, "성도"
    )
    is_pastoral = is_pastoral_applicant(profile)
    status_labels = dict(UserProfile.OnboardingStatus.choices)

    retreat_group_name = ""
    if is_pastoral:
        retreat_group_name = "목회자 — 조원 자동 배정 없음"
    elif profile.requested_retreat_group_id:
        retreat_group_name = profile.requested_retreat_group.name

    application_updated_at = ""
    if getattr(profile, "updated_at", None):
        from django.utils import timezone

        application_updated_at = timezone.localtime(profile.updated_at).strftime(
            "%Y-%m-%d %H:%M"
        )

    return {
        "has_application": True,
        "onboarding_status": profile.onboarding_status,
        "onboarding_status_label": status_labels.get(
            profile.onboarding_status, profile.onboarding_status
        ),
        "region_name": region_name,
        "division_name": div.name if div else "",
        "team_name": profile.requested_team.name if profile.requested_team_id else "",
        "applicant_role_label": applicant_role_label,
        "is_pastoral_applicant": is_pastoral,
        "retreat_participation": bool(profile.requested_retreat_participation),
        "retreat_event_name": (
            profile.requested_retreat_event.name
            if profile.requested_retreat_event_id
            else ""
        ),
        "retreat_group_name": retreat_group_name,
        "onboarding_note": (profile.onboarding_note or "").strip(),
        "application_updated_at": application_updated_at,
    }
