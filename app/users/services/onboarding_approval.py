"""가입 승인 시 목회자 계정(role_level·목회 담당 부서) 자동 반영."""

from __future__ import annotations

from retreat.services.onboarding import is_pastoral_applicant
from users.models import PastoralDivisionAssignment, RoleLevel, UserDivisionTeam, UserProfile


def approve_onboarding_profile(
    profile: UserProfile,
    *,
    changed_by=None,
    onboarding_note: str = "",
    retreat_event_id_raw: str = "",
    retreat_group_id_raw: str = "",
) -> str | None:
    """가입 신청 승인 — 소속 반영·목회자 setup·APPROVED. 오류 시 메시지 반환."""
    if profile is None or not profile.requested_division_id:
        return "신청 부서를 먼저 지정해 주세요."

    team = profile.requested_team
    if team is not None and team.division_id != profile.requested_division_id:
        return "신청 팀은 신청 부서에 속해야 합니다."

    from retreat.services.onboarding import (
        resolve_requested_retreat_assignment,
        sync_retreat_attendee_from_onboarding_profile,
    )

    if (retreat_event_id_raw or "").strip() or (retreat_group_id_raw or "").strip():
        retreat_err = resolve_requested_retreat_assignment(
            profile,
            division=profile.requested_division,
            event_id_raw=(retreat_event_id_raw or "").strip(),
            group_id_raw=(retreat_group_id_raw or "").strip(),
        )
        if retreat_err:
            return retreat_err

    UserDivisionTeam.objects.update_or_create(
        user=profile.user,
        division=profile.requested_division,
        defaults={"team": team, "is_primary": True, "sort_order": 0},
    )
    apply_pastoral_account_setup(profile.user, profile)
    profile.onboarding_status = UserProfile.OnboardingStatus.APPROVED
    profile.onboarding_note = (onboarding_note or "").strip()
    update_fields = ["onboarding_status", "onboarding_note", "updated_at"]
    if (retreat_event_id_raw or "").strip() or (retreat_group_id_raw or "").strip():
        update_fields.extend(
            [
                "requested_retreat_participation",
                "requested_retreat_event",
                "requested_retreat_group",
                "requested_retreat_role",
            ]
        )
    profile.save(update_fields=update_fields)
    sync_retreat_attendee_from_onboarding_profile(
        user=profile.user,
        profile=profile,
        changed_by=changed_by,
    )
    return None


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
