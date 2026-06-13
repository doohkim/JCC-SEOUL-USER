"""조 운영진 멤버십 ↔ 조원 명단 동기화."""

from __future__ import annotations

from retreat.models import RetreatAttendee, RetreatChangeLog, RetreatGroupMembership
from retreat.services.audit import log_retreat_change
from retreat.services.enrollment import enroll_attendee_into_active_sessions
from users.services.user_display import user_display_name


def _profile_for(user):
    return getattr(user, "profile", None)


def sync_attendee_from_membership(
    membership: RetreatGroupMembership,
    *,
    changed_by,
) -> RetreatAttendee:
    """운영진 멤버십에 맞춰 조원 행을 생성·갱신한다."""
    user = membership.user
    group = membership.group
    profile = _profile_for(user)
    name = user_display_name(user) or user.username
    if profile and (profile.real_name or "").strip():
        name = (profile.real_name or "").strip()
    phone = (getattr(profile, "phone", "") or "").strip()

    attendee = (
        RetreatAttendee.objects.filter(group=group, user=user).first()
        or RetreatAttendee.objects.filter(group=group, name=name).first()
    )
    created = attendee is None
    if created:
        attendee = RetreatAttendee(
            group=group,
            name=name,
            check_in_status=RetreatAttendee.CheckInStatus.PENDING,
        )

    attendee.user = user
    attendee.member_role = membership.role
    if phone and not attendee.phone:
        attendee.phone = phone
    if not attendee.name:
        attendee.name = name
    attendee.save()
    enroll_attendee_into_active_sessions(attendee, actor=changed_by)

    log_retreat_change(
        user=changed_by,
        event=group.event,
        action=RetreatChangeLog.Action.CREATE if created else RetreatChangeLog.Action.UPDATE,
        target_type=RetreatChangeLog.TargetType.ATTENDEE,
        target_id=attendee.id,
        payload_after={
            "group_id": group.id,
            "user_id": user.id,
            "member_role": membership.role,
            "source": "group_membership_sync",
        },
    )
    return attendee


def sync_membership_from_attendee(attendee: RetreatAttendee, *, changed_by) -> None:
    """조원 행의 계정·역할에 맞춰 운영진 멤버십을 맞춘다.

    - 계정 연결 + 조장/부조장: 멤버십 생성·갱신 (조장 권한 부여)
    - 계정 연결 + 조원: 멤버십 제거
    - 계정 미연결: 멤버십 없음
    """
    group = attendee.group
    user = attendee.user
    if user is None:
        return

    leader_roles = (
        RetreatAttendee.MemberRole.LEADER,
        RetreatAttendee.MemberRole.VICE_LEADER,
    )
    if attendee.member_role in leader_roles:
        membership, created = RetreatGroupMembership.objects.update_or_create(
            group=group,
            user=user,
            defaults={"role": attendee.member_role},
        )
        log_retreat_change(
            user=changed_by,
            event=group.event,
            action=RetreatChangeLog.Action.CREATE
            if created
            else RetreatChangeLog.Action.UPDATE,
            target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
            target_id=membership.id,
            payload_after={
                "group_id": group.id,
                "user_id": user.id,
                "role": attendee.member_role,
                "source": "attendee_sync",
            },
        )
    else:
        existing = RetreatGroupMembership.objects.filter(
            group=group, user=user
        ).first()
        if existing:
            mid = existing.id
            existing.delete()
            log_retreat_change(
                user=changed_by,
                event=group.event,
                action=RetreatChangeLog.Action.DELETE,
                target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
                target_id=mid,
                payload_before={"group_id": group.id, "user_id": user.id},
            )


def remove_membership_for_attendee(attendee: RetreatAttendee, *, changed_by) -> None:
    """조원 행 삭제 시 연결된 운영진 멤버십도 제거."""
    if attendee.user_id is None:
        return
    existing = RetreatGroupMembership.objects.filter(
        group=attendee.group, user_id=attendee.user_id
    ).first()
    if not existing:
        return
    mid = existing.id
    event = attendee.group.event
    existing.delete()
    log_retreat_change(
        user=changed_by,
        event=event,
        action=RetreatChangeLog.Action.DELETE,
        target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
        target_id=mid,
        payload_before={"group_id": attendee.group_id, "user_id": attendee.user_id},
    )


def delete_attendees_for_membership(
    membership: RetreatGroupMembership,
    *,
    changed_by,
) -> int:
    """운영진 멤버십에 연결된 조원 명단 행을 제거한다.

    admin 에서 운영진(또는 계정)을 삭제할 때 조원 명단까지 함께 정리하는 용도.
    인-앱 '운영진 해제'(``clear_leader_role_on_membership_removed``)와 달리
    조원 행 자체를 삭제한다. 이미 생성된 출석부 스냅샷
    (``RetreatSessionAttendee``)은 ``source_attendee=SET_NULL`` 이라 보존된다.
    """
    group_id = membership.group_id
    user_id = membership.user_id
    if not group_id or not user_id:
        return 0
    removed = 0
    for attendee in list(
        RetreatAttendee.objects.filter(group_id=group_id, user_id=user_id)
    ):
        attendee_id = attendee.id
        event_id = attendee.group.event_id
        attendee.delete()
        removed += 1
        log_retreat_change(
            user=changed_by,
            event=event_id,
            action=RetreatChangeLog.Action.DELETE,
            target_type=RetreatChangeLog.TargetType.ATTENDEE,
            target_id=attendee_id,
            payload_before={
                "group_id": group_id,
                "user_id": user_id,
                "source": "admin_membership_delete",
            },
        )
    return removed


def clear_leader_role_on_membership_removed(
    membership: RetreatGroupMembership,
    *,
    changed_by,
) -> None:
    """운영진 제거 시 조원 행은 유지하고 역할만 조원으로 내린다."""
    group = membership.group
    user = membership.user
    qs = RetreatAttendee.objects.filter(group=group, user=user)
    for attendee in qs:
        if attendee.member_role in (
            RetreatAttendee.MemberRole.LEADER,
            RetreatAttendee.MemberRole.VICE_LEADER,
        ):
            attendee.member_role = RetreatAttendee.MemberRole.MEMBER
            attendee.save(update_fields=["member_role", "updated_at"])
            log_retreat_change(
                user=changed_by,
                event=group.event,
                action=RetreatChangeLog.Action.UPDATE,
                target_type=RetreatChangeLog.TargetType.ATTENDEE,
                target_id=attendee.id,
                payload_after={"member_role": attendee.member_role},
            )
