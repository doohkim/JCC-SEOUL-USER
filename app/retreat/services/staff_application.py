"""운영진 참가 신청 — 상태·허브 카드·승인 처리."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from django.db import transaction
from django.utils import timezone

from retreat.models import (
    RetreatCouncilMembership,
    RetreatEvent,
    RetreatGroup,
    RetreatStaffApplication,
)
from retreat.services.audit import log_retreat_change, serialize_model_fields
from retreat.services.staff_capabilities import AccessLevel, effective_capabilities

if TYPE_CHECKING:
    from users.models import User

StaffEventStatus = Literal[
    "assigned", "approved", "pending", "rejected", "open", "closed"
]


def user_assigned_to_event(user: User, event: RetreatEvent) -> bool:
    if user.retreat_council_memberships.filter(event=event).exists():
        return True
    return user.retreat_group_memberships.filter(group__event=event).exists()


def _latest_application(user: User, event: RetreatEvent) -> RetreatStaffApplication | None:
    return (
        RetreatStaffApplication.objects.filter(event=event, user=user)
        .order_by("-created_at", "-id")
        .first()
    )


def event_staff_status(user: User, event: RetreatEvent) -> StaffEventStatus:
    if user_assigned_to_event(user, event):
        return "assigned"
    application = _latest_application(user, event)
    if application is not None:
        if application.status == RetreatStaffApplication.Status.PENDING:
            return "pending"
        if application.status == RetreatStaffApplication.Status.APPROVED:
            return "approved"
        if application.status == RetreatStaffApplication.Status.REJECTED:
            if event.staff_applications_open:
                return "open"
            return "rejected"
    if event.staff_applications_open:
        return "open"
    return "closed"


def has_retreat_operational_access(user: User, event: RetreatEvent) -> bool:
    caps = effective_capabilities(user, event)
    return any(
        level >= AccessLevel.VIEW
        for level in (
            caps.dashboard,
            caps.groups,
            caps.pickup,
            caps.lodging,
            caps.admin,
        )
    )


StaffEventStatus = Literal[
    "assigned", "approved", "pending", "rejected", "open", "closed"
]
StaffApplicantTier = Literal["pastor", "evangelist", "member"]

_STAFF_TIER_LABELS = {
    "pastor": "목사님",
    "evangelist": "전도사님",
    "member": "성도",
}


def staff_applicant_tier(user: User) -> StaffApplicantTier:
    code = getattr(getattr(user, "role_level", None), "code", None)
    if code == "pastor":
        return "pastor"
    if code == "evangelist":
        return "evangelist"
    return "member"


def staff_applicant_tier_label(tier: StaffApplicantTier) -> str:
    return _STAFF_TIER_LABELS[tier]


def primary_affiliation_for(user: User) -> tuple["Region | None", "Division | None"]:
    """주 소속 지역·부서 (UserDivisionTeam)."""
    from users.models import Division, Region

    row = (
        user.division_teams.order_by(
            "-is_primary", "sort_order", "division__sort_order", "id"
        )
        .select_related("division", "division__region")
        .first()
    )
    if row is None:
        return None, None
    division: Division = row.division
    region: Region = division.region
    return region, division


def eligible_groups_for_member(user: User, event: RetreatEvent) -> list[RetreatGroup]:
    """성도 신청 — 본인 주 소속 부서에 배정된 집회 조만."""
    _region, division = primary_affiliation_for(user)
    if division is None:
        return []
    return list(
        RetreatGroup.objects.filter(event=event, division_id=division.id).order_by(
            "order", "id"
        )
    )


def validate_member_group_choice(
    user: User,
    event: RetreatEvent,
    group: RetreatGroup,
    *,
    division,
) -> None:
    """성도 조 선택 권한·일치 검증."""
    if group.event_id != event.id:
        raise ValueError("이 집회의 조가 아닙니다.")
    if group.division_id != division.id:
        raise ValueError("소속 부서에 해당하지 않는 조입니다.")
    if group.region_id != division.region_id:
        raise ValueError("소속 지역·부서와 조의 지역·부서가 일치하지 않습니다.")
    allowed_ids = {g.id for g in eligible_groups_for_member(user, event)}
    if group.id not in allowed_ids:
        raise ValueError("신청할 수 없는 조입니다.")


def is_pastoral_staff_applicant(user: User) -> bool:
    return staff_applicant_tier(user) in ("pastor", "evangelist")


def suggest_council_role(application: RetreatStaffApplication) -> str:
    if application.division_id:
        return RetreatCouncilMembership.Role.DIVISION_OBSERVER
    return RetreatCouncilMembership.Role.EVENT_OBSERVER


def apply_staff_application(
    application: RetreatStaffApplication,
    *,
    reviewer: User,
    council_role: str | None = None,
) -> RetreatStaffApplication:
    if application.status != RetreatStaffApplication.Status.PENDING:
        raise ValueError("검토 중인 신청만 승인할 수 있습니다.")
    if user_assigned_to_event(application.user, application.event):
        raise ValueError("이미 배정된 사용자입니다.")

    pastoral = is_pastoral_staff_applicant(application.user)
    if pastoral:
        if not application.division_id and not application.region_id:
            raise ValueError("목회자 신청 정보가 없습니다.")
    elif not application.group_id:
        raise ValueError("조 또는 목회자 신청 정보가 없습니다.")

    suggested_role = ""
    if pastoral:
        role = council_role or suggest_council_role(application)
        if role not in dict(RetreatCouncilMembership.Role.choices):
            raise ValueError("올바르지 않은 council 역할입니다.")
        suggested_role = role

    with transaction.atomic():
        before = serialize_model_fields(
            application,
            [
                "status",
                "region",
                "division",
                "group",
                "group_role",
                "approved_council_role",
            ],
        )
        application.approved_council_role = suggested_role
        application.status = RetreatStaffApplication.Status.APPROVED
        application.reviewed_by = reviewer
        application.reviewed_at = timezone.now()
        application.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "approved_council_role",
                "updated_at",
            ]
        )
        log_retreat_change(
            user=reviewer,
            event=application.event,
            action="approve",
            target_type="staff_application",
            target_id=application.id,
            payload_before=before,
            payload_after=serialize_model_fields(
                application,
                ["status", "approved_council_role", "reviewed_by", "reviewed_at"],
            ),
        )
    return application


def reject_staff_application(
    application: RetreatStaffApplication,
    *,
    reviewer: User,
    reason: str = "",
) -> RetreatStaffApplication:
    if application.status != RetreatStaffApplication.Status.PENDING:
        raise ValueError("검토 중인 신청만 반려할 수 있습니다.")
    before = serialize_model_fields(application, ["status", "rejection_reason"])
    application.status = RetreatStaffApplication.Status.REJECTED
    application.rejection_reason = (reason or "").strip()[:500]
    application.reviewed_by = reviewer
    application.reviewed_at = timezone.now()
    application.save(
        update_fields=[
            "status",
            "rejection_reason",
            "reviewed_by",
            "reviewed_at",
            "updated_at",
        ]
    )
    log_retreat_change(
        user=reviewer,
        event=application.event,
        action="reject",
        target_type="staff_application",
        target_id=application.id,
        payload_before=before,
        payload_after=serialize_model_fields(
            application,
            ["status", "rejection_reason", "reviewed_by", "reviewed_at"],
        ),
    )
    return application


def groups_for_staff_apply(event: RetreatEvent, *, division_id: int) -> list[RetreatGroup]:
    return list(
        RetreatGroup.objects.filter(event=event, division_id=division_id).order_by(
            "order", "id"
        )
    )


def member_can_apply_to_event(user: User, event: RetreatEvent) -> tuple[bool, str]:
    """성도 신청 가능 여부와 안내 메시지."""
    if staff_applicant_tier(user) != "member":
        return True, ""
    region, division = primary_affiliation_for(user)
    if division is None:
        return False, "소속 지역·부서가 등록되어 있지 않습니다. 계정 관리자에게 문의해 주세요."
    groups = eligible_groups_for_member(user, event)
    if not groups:
        affiliation = f"{region.name} {division.name}" if region else division.name
        return (
            False,
            f'귀하의 소속 부서({affiliation}) 운영진 조가 없습니다. '
            f'"{event.name}" 집회 운영진에게 문의해 주세요.',
        )
    return True, ""
