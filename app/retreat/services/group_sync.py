"""조 운영진 멤버십 ↔ 조원 명단 동기화."""

from __future__ import annotations

from retreat.models import (
    RetreatAttendee,
    RetreatChangeLog,
    RetreatGroup,
    RetreatGroupMembership,
)
from retreat.services.audit import log_retreat_change
from retreat.services.enrollment import enroll_attendee_into_active_sessions
from retreat.services.lodging_stay import persist_lodging_stay_status
from retreat.services.pickup_attendee import delete_pickups_for_attendee
from users.services.user_display import user_display_name
from users.validators import normalize_korea_mobile_phone


def _profile_for(user):
    return getattr(user, "profile", None)


def attendee_profile_defaults_for_user(user) -> dict[str, str]:
    """연결된 사용자 프로필에서 조원 기본 필드를 추출한다."""
    profile = _profile_for(user)
    name = user_display_name(user) or user.username
    if profile and (profile.real_name or "").strip():
        name = (profile.real_name or "").strip()
    phone = (getattr(profile, "phone", "") or "").strip()
    normalized_phone = normalize_korea_mobile_phone(phone) if phone else ""
    if normalized_phone:
        phone = normalized_phone
    gender = (getattr(profile, "gender", "") or "").strip()
    if gender not in dict(RetreatAttendee.Gender.choices):
        gender = ""
    return {"name": name, "phone": phone, "gender": gender}


def apply_attendee_profile_defaults(
    validated_data: dict,
    user,
    *,
    instance=None,
    overwrite: bool = False,
) -> dict:
    """사용자 프로필 값으로 조원 필드를 채운다.

    overwrite=True 이면 계정 연결·변경 시 프로필로 덮어쓴다.
    """
    if not user:
        return validated_data
    defaults = attendee_profile_defaults_for_user(user)
    for field in ("name", "phone", "gender"):
        incoming = validated_data.get(field)
        if incoming is None and instance is not None:
            incoming = getattr(instance, field, "")
        if overwrite:
            if field == "name":
                if defaults[field]:
                    validated_data[field] = defaults[field]
            elif defaults.get(field):
                validated_data[field] = defaults[field]
            continue
        if field == "name":
            if not (incoming or "").strip():
                validated_data[field] = defaults[field]
        elif not incoming:
            validated_data[field] = defaults[field]
    return validated_data


def duplicate_event_attendees_for_user(user, *, event_id: int, exclude_pk: int | None = None):
    """같은 집회에서 user 가 연결된 다른 조원 행."""
    qs = RetreatAttendee.objects.filter(
        user_id=user.pk,
        group__event_id=event_id,
    ).select_related("group")
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs


def remove_stale_attendees_for_user_in_event(
    *,
    user,
    event_id: int,
    keep_group_id: int,
    changed_by,
) -> int:
    """같은 집회 내 다른 조에 남아 있는 조원 행을 제거한다."""
    removed = 0
    for attendee in list(
        duplicate_event_attendees_for_user(user, event_id=event_id).exclude(
            group_id=keep_group_id
        )
    ):
        attendee_id = attendee.id
        group_id = attendee.group_id
        delete_pickups_for_attendee(attendee, changed_by=changed_by)
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
                "user_id": user.pk,
                "source": "event_attendee_consolidation",
            },
        )
    return removed


def remove_stale_memberships_for_user_in_event(
    *,
    user,
    event_id: int,
    keep_group_id: int,
    changed_by,
) -> int:
    """같은 집회 내 다른 조 운영진 멤버십을 제거한다."""
    removed = 0
    for membership in list(
        RetreatGroupMembership.objects.filter(
            user=user,
            group__event_id=event_id,
        )
        .exclude(group_id=keep_group_id)
        .select_related("group")
    ):
        mid = membership.id
        group_id = membership.group_id
        membership.delete()
        removed += 1
        log_retreat_change(
            user=changed_by,
            event=event_id,
            action=RetreatChangeLog.Action.DELETE,
            target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
            target_id=mid,
            payload_before={
                "group_id": group_id,
                "user_id": user.pk,
                "source": "event_attendee_consolidation",
            },
        )
    return removed


def sync_profile_retreat_group(user, group: RetreatGroup) -> bool:
    """레거시 프로필 미러 — 런타임 단일 진실은 집회별 멤버십 테이블."""
    return False


def consolidate_user_to_event_group(
    user,
    group: RetreatGroup,
    *,
    changed_by,
) -> None:
    """집회당 user → 조 1행·멤버십·프로필을 현재 조 기준으로 정리한다."""
    if user is None or not user.pk:
        return
    remove_stale_attendees_for_user_in_event(
        user=user,
        event_id=group.event_id,
        keep_group_id=group.id,
        changed_by=changed_by,
    )
    remove_stale_memberships_for_user_in_event(
        user=user,
        event_id=group.event_id,
        keep_group_id=group.id,
        changed_by=changed_by,
    )
    sync_profile_retreat_group(user, group)


def _delete_group_membership(
    group: RetreatGroup,
    user_id: int,
    *,
    changed_by,
) -> None:
    existing = RetreatGroupMembership.objects.filter(
        group=group, user_id=user_id
    ).first()
    if not existing:
        return
    mid = existing.id
    uid = existing.user_id
    existing.delete()
    log_retreat_change(
        user=changed_by,
        event=group.event,
        action=RetreatChangeLog.Action.DELETE,
        target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
        target_id=mid,
        payload_before={"group_id": group.id, "user_id": uid},
    )


def sync_attendee_from_membership(
    membership: RetreatGroupMembership,
    *,
    changed_by,
) -> RetreatAttendee:
    """운영진 멤버십에 맞춰 조원 행을 생성·갱신한다."""
    user = membership.user
    group = membership.group
    defaults = attendee_profile_defaults_for_user(user)
    name = defaults["name"]
    phone = defaults["phone"]
    gender = defaults["gender"]

    attendee = RetreatAttendee.objects.filter(group=group, user=user).first()
    if attendee is None:
        by_name = RetreatAttendee.objects.filter(group=group, name=name).first()
        if by_name is not None and by_name.user_id != user.id:
            # 계정 연결 해제·다른 계정 연결된 조원 행은 재연결하지 않는다.
            return by_name
        attendee = by_name
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
    if gender and not attendee.gender:
        attendee.gender = gender
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
    consolidate_user_to_event_group(user, group, changed_by=changed_by)
    persist_lodging_stay_status(attendee)
    return attendee


def sync_membership_from_attendee(
    attendee: RetreatAttendee,
    *,
    changed_by,
    previous_user_id: int | None = None,
    previous_member_role: str | None = None,
) -> None:
    """조원 행의 계정·역할에 맞춰 운영진 멤버십을 맞춘다.

    - 계정 연결 + 조장/부조장: 멤버십 생성·갱신 (조장 권한 부여)
    - 계정 연결 + 조원: 멤버십 제거
    - 계정 해제: 이전 조장/부조장 사용자 멤버십 제거
    - 계정 변경: 이전 조장/부조장 사용자 멤버십 제거 후 새 사용자 반영
    """
    group = attendee.group
    user = attendee.user
    leader_roles = (
        RetreatAttendee.MemberRole.LEADER,
        RetreatAttendee.MemberRole.VICE_LEADER,
    )
    prev_role = (previous_member_role or "").strip()
    current_user_id = user.id if user else None
    if previous_user_id and previous_user_id != current_user_id:
        if prev_role in leader_roles or attendee.member_role in leader_roles:
            _delete_group_membership(group, previous_user_id, changed_by=changed_by)

    if user is None:
        return

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
    consolidate_user_to_event_group(user, group, changed_by=changed_by)


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
        RetreatAttendee.objects.filter(group_id=group_id, user_id=user_id).select_related(
            "group", "group__event"
        )
    ):
        attendee_id = attendee.id
        event_id = attendee.group.event_id
        delete_pickups_for_attendee(attendee, changed_by=changed_by)
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
