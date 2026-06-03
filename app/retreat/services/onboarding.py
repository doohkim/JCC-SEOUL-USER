"""온보딩 승인 시 수련회 멤버십·조원 연동."""

from __future__ import annotations

from retreat.models import (
    RetreatAttendee,
    RetreatChangeLog,
    RetreatGroup,
    RetreatGroupMembership,
)
from retreat.services.audit import log_retreat_change
from retreat.services.group_sync import sync_attendee_from_membership
from users.services.user_display import user_display_name

RETREAT_ROLE_LABELS = {
    "": "참가자",
    "participant": "참가자",
    "leader": "조장",
    "vice_leader": "부조장",
}


def _attendee_name_for_user(user, profile) -> str:
    return user_display_name(user) or user.username


def _ensure_attendee_for_group(
    *,
    group: RetreatGroup,
    user,
    profile,
    changed_by,
) -> RetreatAttendee | None:
    """조원 명단에 사용자를 반영한다 (이름 기준 중복 방지)."""
    name = _attendee_name_for_user(user, profile)
    phone = (getattr(profile, "phone", "") or "").strip()
    gender = (getattr(profile, "gender", "") or "").strip()
    if gender not in dict(RetreatAttendee.Gender.choices):
        gender = ""

    role_code = (getattr(profile, "requested_retreat_role", "") or "").strip()
    member_role = RetreatAttendee.MemberRole.MEMBER
    if role_code in (
        RetreatGroupMembership.Role.LEADER,
        RetreatGroupMembership.Role.VICE_LEADER,
    ):
        member_role = role_code

    existing = (
        RetreatAttendee.objects.filter(group=group, user=user).first()
        or RetreatAttendee.objects.filter(group=group, name=name).first()
    )
    if existing:
        updated_fields = []
        existing.user = user
        updated_fields.append("user")
        if member_role != RetreatAttendee.MemberRole.MEMBER:
            existing.member_role = member_role
            updated_fields.append("member_role")
        if phone and not existing.phone:
            existing.phone = phone
            updated_fields.append("phone")
        if gender and not existing.gender:
            existing.gender = gender
            updated_fields.append("gender")
        if updated_fields:
            existing.save(update_fields=updated_fields + ["updated_at"])
        attendee = existing
        created = False
    else:
        attendee = RetreatAttendee.objects.create(
            group=group,
            user=user,
            member_role=member_role,
            name=name,
            phone=phone,
            gender=gender,
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
        )
        created = True

    log_retreat_change(
        user=changed_by,
        event=group.event,
        action=RetreatChangeLog.Action.CREATE
        if created
        else RetreatChangeLog.Action.UPDATE,
        target_type=RetreatChangeLog.TargetType.ATTENDEE,
        target_id=attendee.id,
        payload_after={
            "group_id": group.id,
            "name": attendee.name,
            "user_id": user.id,
            "source": "onboarding_approval",
        },
    )
    return attendee


def apply_retreat_membership_on_approval(
    *,
    user,
    profile,
    retreat_group_id: str | None,
    retreat_role: str | None,
    changed_by,
) -> None:
    """승인 시 수련회 조 배정.

    - 조장·부조장: ``RetreatGroupMembership`` + ``RetreatAttendee``
    - 일반 참가자(participant/빈 역할): ``RetreatAttendee`` 만
    """
    if not profile.requested_retreat_participation:
        return
    group_id_raw = retreat_group_id or getattr(
        profile, "requested_retreat_group_id", None
    )
    if not group_id_raw or not str(group_id_raw).isdigit():
        return

    group = RetreatGroup.objects.filter(pk=int(group_id_raw)).first()
    if group is None:
        return
    if profile.requested_retreat_event_id and group.event_id != profile.requested_retreat_event_id:
        return

    role = (retreat_role or profile.requested_retreat_role or "participant").strip()
    if role not in ("", "participant"):
        if role not in (
            RetreatGroupMembership.Role.LEADER,
            RetreatGroupMembership.Role.VICE_LEADER,
        ):
            role = "participant"

    if role in (
        RetreatGroupMembership.Role.LEADER,
        RetreatGroupMembership.Role.VICE_LEADER,
    ):
        membership, created = RetreatGroupMembership.objects.update_or_create(
            user=profile.user,
            group=group,
            defaults={"role": role},
        )
        sync_attendee_from_membership(membership, changed_by=changed_by)
        log_retreat_change(
            user=changed_by,
            event=group.event,
            action=RetreatChangeLog.Action.CREATE
            if created
            else RetreatChangeLog.Action.UPDATE,
            target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
            target_id=membership.id,
            payload_before=None if created else {"role": role},
            payload_after={
                "user_id": profile.user_id,
                "group_id": group.id,
                "role": role,
            },
        )

    _ensure_attendee_for_group(
        group=group,
        user=user,
        profile=profile,
        changed_by=changed_by,
    )
