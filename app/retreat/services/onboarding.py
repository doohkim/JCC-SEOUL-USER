"""온보딩 승인 시 수련회 멤버십·조원 연동."""

from __future__ import annotations

from retreat.models import (
    RetreatAttendee,
    RetreatChangeLog,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
)
from retreat.services.audit import log_retreat_change
from retreat.services.group_sync import sync_attendee_from_membership
from users.models import UserProfile
from users.services.user_display import user_display_name

RETREAT_ROLE_LABELS = {
    "": "참가자",
    "participant": "참가자",
    "leader": "조장",
    "vice_leader": "부조장",
}


def _attendee_name_for_user(user, profile) -> str:
    real_name = (getattr(profile, "real_name", "") or "").strip()
    if real_name:
        return real_name
    return user_display_name(user) or user.username


def resolve_requested_retreat_assignment(
    profile,
    *,
    division,
    event_id_raw: str = "",
    group_id_raw: str = "",
) -> str | None:
    """가입신청서·승인 처리에서 수련회 조 배정을 profile에 반영.

    POST에 집회/조 id가 없으면 기존 profile 값을 유지한다.
    오류 시 사용자 메시지를 반환한다.
    """
    event_id_raw = (event_id_raw or "").strip()
    group_id_raw = (group_id_raw or "").strip()
    if not event_id_raw and not group_id_raw:
        return None

    retreat_event = None
    retreat_group = None

    if event_id_raw.isdigit():
        retreat_event = RetreatEvent.objects.filter(
            pk=int(event_id_raw), is_active=True
        ).first()
        if retreat_event is None:
            return "선택한 수련회 집회를 찾을 수 없습니다."

    if group_id_raw.isdigit():
        retreat_group = (
            RetreatGroup.objects.filter(pk=int(group_id_raw))
            .select_related("event")
            .first()
        )
        if retreat_group is None:
            return "선택한 수련회 조를 찾을 수 없습니다."
        if division and retreat_group.division_id != division.id:
            return "선택한 조는 신청 부서에 속해야 합니다."
        if retreat_event and retreat_group.event_id != retreat_event.id:
            return "선택한 조는 선택한 집회에 속해야 합니다."
        if retreat_event is None:
            retreat_event = retreat_group.event

    retreat_participation = bool(retreat_event and retreat_group)
    if event_id_raw and group_id_raw and not retreat_participation:
        return "수련회 집회와 조를 함께 선택해 주세요."

    profile.requested_retreat_participation = retreat_participation
    profile.requested_retreat_event = retreat_event if retreat_participation else None
    profile.requested_retreat_group = retreat_group if retreat_participation else None
    profile.requested_retreat_role = ""
    return None


def _ensure_attendee_for_group(
    *,
    group: RetreatGroup,
    user,
    profile,
    changed_by,
    member_role: str | None = None,
) -> RetreatAttendee | None:
    """조원 명단에 사용자를 반영한다 (이름 기준 중복 방지)."""
    name = _attendee_name_for_user(user, profile)
    phone = (getattr(profile, "phone", "") or "").strip()
    gender = (getattr(profile, "gender", "") or "").strip()
    if gender not in dict(RetreatAttendee.Gender.choices):
        gender = ""

    if member_role is None:
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
        if user and existing.user_id != user.id:
            existing.user = user
            updated_fields.append("user")
        if name and existing.name != name:
            existing.name = name
            updated_fields.append("name")
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


def retreat_attendee_exists_for_profile(profile) -> bool:
    if not profile.user_id or not profile.requested_retreat_group_id:
        return False
    return RetreatAttendee.objects.filter(
        group_id=profile.requested_retreat_group_id,
        user_id=profile.user_id,
    ).exists()


def sync_retreat_attendee_from_onboarding_profile(
    *,
    user,
    profile,
    changed_by,
) -> None:
    """가입 승인·신청서에 저장된 수련회 조를 조원 명단(RetreatAttendee)에 반영한다."""
    if profile.onboarding_status != UserProfile.OnboardingStatus.APPROVED:
        return
    apply_retreat_membership_on_approval(
        user=user,
        profile=profile,
        retreat_group_id=None,
        retreat_role=None,
        changed_by=changed_by,
        appoint_leadership=False,
    )


def apply_retreat_membership_on_approval(
    *,
    user,
    profile,
    retreat_group_id: str | None,
    retreat_role: str | None,
    changed_by,
    appoint_leadership: bool = False,
) -> None:
    """승인 시 수련회 조 배정.

    - ``appoint_leadership=False`` (가입신청서 승인): ``RetreatAttendee`` 만, 항상 조원
    - ``appoint_leadership=True`` (계정 관리 수동 지정): 조장·부조장 시 ``RetreatGroupMembership`` + ``RetreatAttendee``
    """
    group_id_raw = retreat_group_id or getattr(
        profile, "requested_retreat_group_id", None
    )
    if not group_id_raw or not str(group_id_raw).isdigit():
        return

    group = RetreatGroup.objects.filter(pk=int(group_id_raw)).first()
    if group is None:
        return
    if (
        profile.requested_retreat_event_id
        and group.event_id != profile.requested_retreat_event_id
    ):
        return
    if not profile.user_id:
        return

    attendee_member_role = RetreatAttendee.MemberRole.MEMBER
    if appoint_leadership:
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
            attendee_member_role = role

    _ensure_attendee_for_group(
        group=group,
        user=user,
        profile=profile,
        changed_by=changed_by,
        member_role=attendee_member_role,
    )
