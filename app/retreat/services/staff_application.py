"""운영진 참가 신청 — 상태·허브 카드·승인 처리."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from retreat.models import (
    RetreatCouncilMembership,
    RetreatChangeLog,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
    RetreatStaffApplication,
)
from retreat.services.audit import log_retreat_change, serialize_model_fields
from retreat.services.group_sync import sync_attendee_from_membership
from retreat.services.staff_capabilities import AccessLevel, effective_capabilities
from retreat.services.staff_roster import (
    CouncilScopeError,
    assert_can_assign_event_staff,
    resolve_council_staff_scope,
)

if TYPE_CHECKING:
    from users.models import User

StaffEventStatus = Literal[
    "assigned", "approved", "pending", "rejected", "open", "closed"
]


def user_assigned_to_event(user: User, event: RetreatEvent) -> bool:
    if user.retreat_council_memberships.filter(event=event).exists():
        return True
    return user.retreat_group_memberships.filter(group__event=event).exists()


def _latest_application(
    user: User, event: RetreatEvent
) -> RetreatStaffApplication | None:
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
    """성도 신청 — 주 소속 (지역·부서)가 조 담당 범위(대표+보조)에 포함된 집회 조."""
    region, division = primary_affiliation_for(user)
    if region is None or division is None:
        return []
    return list(
        RetreatGroup.objects.filter(event=event)
        .filter(
            Q(region_id=region.id, division_id=division.id)
            | Q(
                extra_scopes__region_id=region.id,
                extra_scopes__division_id=division.id,
            )
        )
        .select_related("region", "division")
        .distinct()
        .order_by("order", "id")
    )


def validate_member_group_choice(
    user: User,
    event: RetreatEvent,
    group: RetreatGroup,
    *,
    region,
    division,
    eligible_groups: list[RetreatGroup] | None = None,
) -> None:
    """성도 조 선택 권한·일치 검증."""
    if group.event_id != event.id:
        raise ValueError("이 집회의 조가 아닙니다.")
    affiliation_pair = (region.id, division.id)
    if affiliation_pair not in group.scope_pairs():
        raise ValueError("소속 지역·부서에 해당하지 않는 조입니다.")
    allowed_ids = {
        g.id
        for g in (
            eligible_groups
            if eligible_groups is not None
            else eligible_groups_for_member(user, event)
        )
    }
    if group.id not in allowed_ids:
        raise ValueError("신청할 수 없는 조입니다.")


def is_pastoral_staff_applicant(user: User) -> bool:
    return staff_applicant_tier(user) in ("pastor", "evangelist")


def suggest_council_role(application: RetreatStaffApplication) -> str:
    if application.division_id:
        return RetreatCouncilMembership.Role.DIVISION_OBSERVER
    return RetreatCouncilMembership.Role.EVENT_OBSERVER


def is_council_track_application(application: RetreatStaffApplication) -> bool:
    """집회 운영진 신청 — 목회자 또는 application_track=council."""
    if is_pastoral_staff_applicant(application.user):
        return True
    from retreat.models import StaffApplicationTrack

    return application.application_track == StaffApplicationTrack.COUNCIL


def is_group_leadership_application(application: RetreatStaffApplication) -> bool:
    from retreat.models import StaffApplicationTrack

    return application.application_track == StaffApplicationTrack.GROUP_LEADERSHIP


def _provision_group_leadership_from_staff_application(
    application: RetreatStaffApplication,
    *,
    reviewer: User,
) -> None:
    """참가 신청 승인 시 조장·부조장 멤버십·조원 반영 (승인 처리에서만 호출)."""
    if is_pastoral_staff_applicant(application.user):
        return
    if not application.group_id:
        return
    role = (application.group_role or "").strip()
    if role not in (
        RetreatGroupMembership.Role.LEADER,
        RetreatGroupMembership.Role.VICE_LEADER,
    ):
        return

    group = application.group
    membership, created = RetreatGroupMembership.objects.update_or_create(
        group=group,
        user=application.user,
        defaults={"role": role},
    )
    log_retreat_change(
        user=reviewer,
        event=application.event,
        action=(
            RetreatChangeLog.Action.CREATE
            if created
            else RetreatChangeLog.Action.UPDATE
        ),
        target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
        target_id=membership.id,
        payload_after={
            "group_id": group.id,
            "user_id": application.user_id,
            "role": role,
            "source": "staff_application_approval",
        },
    )
    sync_attendee_from_membership(membership, changed_by=reviewer)


def _provision_council_from_staff_application(
    application: RetreatStaffApplication,
    *,
    reviewer: User,
) -> None:
    """참가 신청 승인 시 council 멤버십 반영 (목회자·집회 운영진 신청)."""
    if not is_council_track_application(application):
        return
    role = (application.approved_council_role or "").strip()
    if not role:
        return
    if role not in dict(RetreatCouncilMembership.Role.choices):
        raise ValueError("올바르지 않은 council 역할입니다.")
    try:
        region_id, division_id = resolve_council_staff_scope(
            role,
            region_id=application.region_id,
            division_id=application.division_id,
        )
    except CouncilScopeError as exc:
        raise ValueError(str(exc)) from exc

    assert_can_assign_event_staff(application.user, application.event, kind="council")
    membership, created = RetreatCouncilMembership.objects.update_or_create(
        event=application.event,
        user=application.user,
        defaults={
            "role": role,
            "note": "",
            "region_id": region_id,
            "division_id": division_id,
        },
    )
    if created:
        membership.created_by = reviewer
        membership.save(update_fields=["created_by"])
    log_retreat_change(
        user=reviewer,
        event=application.event,
        action=(
            RetreatChangeLog.Action.CREATE
            if created
            else RetreatChangeLog.Action.UPDATE
        ),
        target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
        target_id=membership.id,
        payload_after={
            "staff": True,
            "user_id": application.user_id,
            "role": role,
            "region_id": region_id,
            "division_id": division_id,
            "source": "staff_application_approval",
        },
    )


def eligible_groups_payload_for_member(
    user: User, event: RetreatEvent
) -> list[dict[str, object]]:
    """관리자 승인 UI용 — 신청자 소속 기준 선택 가능 조 목록."""
    return [
        {
            "id": g.id,
            "name": g.name,
            "region_name": g.region.name,
            "division_name": g.division.name,
        }
        for g in eligible_groups_for_member(user, event)
    ]


def _resolve_approval_group_and_role(
    application: RetreatStaffApplication,
    *,
    group_id: int | None,
    group_role: str | None,
) -> tuple[RetreatGroup, str]:
    """승인 시 최종 조·역할 (관리자 override 또는 신청값)."""
    role = (
        group_role if group_role is not None else application.group_role or ""
    ).strip()
    if role not in (
        RetreatGroupMembership.Role.LEADER,
        RetreatGroupMembership.Role.VICE_LEADER,
    ):
        raise ValueError("조장 또는 부조장 역할을 선택해 주세요.")

    target_group_id = group_id if group_id is not None else application.group_id
    if not target_group_id:
        raise ValueError("조를 선택해 주세요.")

    group = RetreatGroup.objects.filter(
        pk=target_group_id, event_id=application.event_id
    ).first()
    if group is None:
        raise ValueError("이 집회의 조가 아닙니다.")

    region, division = primary_affiliation_for(application.user)
    if region is None or division is None:
        raise ValueError("신청자 소속 정보가 없습니다.")
    eligible = eligible_groups_for_member(application.user, application.event)
    validate_member_group_choice(
        application.user,
        application.event,
        group,
        region=region,
        division=division,
        eligible_groups=eligible,
    )
    return group, role


def delete_staff_application_if_unassigned(
    user: User,
    event: RetreatEvent,
    *,
    actor: User,
) -> bool:
    """집회 운영 배정이 없으면 APPROVED 참가 신청서 삭제(재신청 가능)."""
    from retreat.services.staff_roster import user_assigned_to_event_staff

    if user_assigned_to_event_staff(user, event):
        return False

    apps = list(
        RetreatStaffApplication.objects.filter(
            event=event,
            user=user,
            status=RetreatStaffApplication.Status.APPROVED,
        )
    )
    if not apps:
        return False

    for app in apps:
        log_retreat_change(
            user=actor,
            event=event,
            action=RetreatChangeLog.Action.DELETE,
            target_type="staff_application",
            target_id=app.id,
            payload_before=serialize_model_fields(
                app, ["status", "group", "group_role", "user"]
            ),
        )
        app.delete()
    return True


def apply_staff_application(
    application: RetreatStaffApplication,
    *,
    reviewer: User,
    council_role: str | None = None,
    group_id: int | None = None,
    group_role: str | None = None,
) -> RetreatStaffApplication:
    if application.status != RetreatStaffApplication.Status.PENDING:
        raise ValueError("검토 중인 신청만 승인할 수 있습니다.")
    if user_assigned_to_event(application.user, application.event):
        raise ValueError("이미 배정된 사용자입니다.")

    pastoral = is_pastoral_staff_applicant(application.user)
    council_track = is_council_track_application(application)
    resolved_group = None
    resolved_role = ""
    if council_track:
        if not application.division_id and not application.region_id:
            raise ValueError("신청 정보가 없습니다.")
    else:
        resolved_group, resolved_role = _resolve_approval_group_and_role(
            application, group_id=group_id, group_role=group_role
        )

    suggested_role = ""
    if council_track:
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
                "application_track",
                "group",
                "group_role",
                "approved_council_role",
            ],
        )
        if resolved_group is not None:
            application.group = resolved_group
            application.group_role = resolved_role
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
                "group",
                "group_role",
                "updated_at",
            ]
        )
        _provision_group_leadership_from_staff_application(
            application, reviewer=reviewer
        )
        _provision_council_from_staff_application(application, reviewer=reviewer)
        log_retreat_change(
            user=reviewer,
            event=application.event,
            action="approve",
            target_type="staff_application",
            target_id=application.id,
            payload_before=before,
            payload_after=serialize_model_fields(
                application,
                [
                    "status",
                    "group",
                    "group_role",
                    "approved_council_role",
                    "reviewed_by",
                    "reviewed_at",
                ],
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


def groups_for_staff_apply(
    event: RetreatEvent, *, division_id: int
) -> list[RetreatGroup]:
    return list(
        RetreatGroup.objects.filter(event=event, division_id=division_id).order_by(
            "order", "id"
        )
    )


def member_can_apply_to_event(
    user: User,
    event: RetreatEvent,
    *,
    eligible_groups: list[RetreatGroup] | None = None,
) -> tuple[bool, str]:
    """성도 신청 가능 여부와 안내 메시지."""
    if staff_applicant_tier(user) != "member":
        return True, ""
    region, division = primary_affiliation_for(user)
    if division is None:
        return (
            False,
            "소속 지역·부서가 등록되어 있지 않습니다. 계정 관리자에게 문의해 주세요.",
        )
    groups = (
        eligible_groups
        if eligible_groups is not None
        else eligible_groups_for_member(user, event)
    )
    if not groups:
        affiliation = f"{region.name} {division.name}" if region else division.name
        return (
            False,
            f"귀하의 소속 부서({affiliation}) 운영진 조가 없습니다. "
            f'"{event.name}" 집회 운영진에게 문의해 주세요.',
        )
    return True, ""
