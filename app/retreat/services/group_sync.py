"""조 운영진 멤버십 ↔ 조원 명단 동기화.

정책:
- 집회당 ``RetreatAttendee``(소속 조)는 사용자당 1행만.
- 소속이 조장/부조장이면 타조 조장 임명 시 소속 유지·권한만 추가(겸직).
- 소속이 조원이면 타조 조장 임명 시 소속을 그 조로 이동.
- ``RetreatGroupMembership``(조장/부조장 권한)은 여러 조에 부여 가능.
"""

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
from retreat.services.pickup_attendee import (
    delete_pickups_for_attendee,
    pickups_for_attendee,
)
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


def duplicate_event_attendees_for_user(
    user, *, event_id: int, exclude_pk: int | None = None
):
    """같은 집회에서 user 가 연결된 다른 조원 행."""
    qs = RetreatAttendee.objects.filter(
        user_id=user.pk,
        group__event_id=event_id,
    ).select_related("group")
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs


def home_attendee_for_user_in_event(user, *, event_id: int) -> RetreatAttendee | None:
    """집회당 사용자 소속 조원 행(대표조). 없으면 None."""
    if user is None or not getattr(user, "pk", None):
        return None
    return (
        RetreatAttendee.objects.filter(user_id=user.pk, group__event_id=event_id)
        .select_related("group")
        .order_by("id")
        .first()
    )


def home_group_meta_for_user(*, user, event_id: int, assigned_group_id: int) -> dict:
    """운영진 API/UI용 소속 조 메타."""
    home = home_attendee_for_user_in_event(user, event_id=event_id)
    if home is None:
        return {
            "home_group_id": None,
            "home_group_name": "",
            "is_cross_group_leader": False,
        }
    return {
        "home_group_id": home.group_id,
        "home_group_name": home.group.name,
        "is_cross_group_leader": home.group_id != assigned_group_id,
    }


def remove_stale_attendees_for_user_in_event(
    *,
    user,
    event_id: int,
    keep_group_id: int,
    changed_by,
) -> int:
    """같은 집회 내 다른 조에 남아 있는 조원 행을 제거한다.

    소속 조 이동·중복 정리용. 운영진 복수 배정 시에는 호출하지 않는다.
    """
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
    """같은 집회 내 다른 조 운영진 멤버십을 제거한다.

    레거시 호환용. 복수 조장 정책에서는 기본적으로 호출하지 않는다.
    """
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
    remove_other_memberships: bool = False,
) -> None:
    """집회당 user → 조원 행을 현재 조 기준으로 정리한다.

    기본적으로 다른 조 운영진 멤버십은 유지한다.
    ``remove_other_memberships=True`` 는 레거시/명시적 정리용.
    """
    if user is None or not user.pk:
        return
    remove_stale_attendees_for_user_in_event(
        user=user,
        event_id=group.event_id,
        keep_group_id=group.id,
        changed_by=changed_by,
    )
    if remove_other_memberships:
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


def _upsert_attendee_in_group(
    *,
    group: RetreatGroup,
    user,
    member_role: str,
    changed_by,
    source: str,
) -> RetreatAttendee:
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
    attendee.member_role = member_role
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
        action=(
            RetreatChangeLog.Action.CREATE
            if created
            else RetreatChangeLog.Action.UPDATE
        ),
        target_type=RetreatChangeLog.TargetType.ATTENDEE,
        target_id=attendee.id,
        payload_after={
            "group_id": group.id,
            "user_id": user.id,
            "member_role": member_role,
            "source": source,
        },
    )
    persist_lodging_stay_status(attendee)
    return attendee


_LEADER_ROLES = frozenset(
    {
        RetreatAttendee.MemberRole.LEADER,
        RetreatAttendee.MemberRole.VICE_LEADER,
    }
)


def _transfer_pickups_to_group(
    *,
    old_attendee: RetreatAttendee,
    new_group: RetreatGroup,
    new_name: str,
    changed_by,
) -> int:
    """이전 조·이름 픽업을 새 조로 옮긴다 (이름 유지)."""
    moved = 0
    for pickup in list(pickups_for_attendee(old_attendee)):
        before_group = pickup.group_id
        pickup.group = new_group
        if new_name and pickup.name != new_name:
            pickup.name = new_name
        pickup.save(update_fields=["group", "name", "updated_at"])
        moved += 1
        log_retreat_change(
            user=changed_by,
            event=new_group.event_id,
            action=RetreatChangeLog.Action.UPDATE,
            target_type=RetreatChangeLog.TargetType.PICKUP,
            target_id=pickup.id,
            payload_before={"group_id": before_group},
            payload_after={
                "group_id": new_group.id,
                "name": pickup.name,
                "source": "home_group_move",
            },
        )
    return moved


def move_home_attendee_to_group(
    *,
    home: RetreatAttendee,
    target_group: RetreatGroup,
    member_role: str,
    changed_by,
) -> RetreatAttendee:
    """조원 소속을 target_group 으로 옮긴다.

    - 입실·프로필 필드 유지
    - 숙소는 미배정
    - 픽업은 새 조로 group 이전
    - 이전 조 명단 행 삭제
    """
    user = home.user
    old_group_id = home.group_id
    old_pk = home.id

    copy_fields = {
        "name": home.name,
        "phone": home.phone,
        "gender": home.gender,
        "memo": home.memo,
        "check_in_status": home.check_in_status,
        "expected_check_in_at": home.expected_check_in_at,
        "expected_check_out_at": home.expected_check_out_at,
        "checked_in_at": home.checked_in_at,
        "checked_out_at": home.checked_out_at,
        "participation_status": home.participation_status,
    }

    _transfer_pickups_to_group(
        old_attendee=home,
        new_group=target_group,
        new_name=copy_fields["name"],
        changed_by=changed_by,
    )

    # 이전 조 명단 삭제 (픽업은 이미 이전됨 — delete_pickups 호출하지 않음)
    home.delete()
    log_retreat_change(
        user=changed_by,
        event=target_group.event_id,
        action=RetreatChangeLog.Action.DELETE,
        target_type=RetreatChangeLog.TargetType.ATTENDEE,
        target_id=old_pk,
        payload_before={
            "group_id": old_group_id,
            "user_id": user.id if user else None,
            "source": "home_group_move",
        },
    )

    existing = None
    if user:
        existing = RetreatAttendee.objects.filter(group=target_group, user=user).first()
    if existing is None:
        existing = RetreatAttendee.objects.filter(
            group=target_group, name=copy_fields["name"]
        ).first()
        if existing is not None and user and existing.user_id not in (None, user.id):
            existing = None

    created = existing is None
    if created:
        attendee = RetreatAttendee(group=target_group, **copy_fields)
    else:
        attendee = existing
        for key, value in copy_fields.items():
            setattr(attendee, key, value)

    if user:
        attendee.user = user
    attendee.member_role = member_role
    attendee.lodging_room = None
    attendee.save()
    enroll_attendee_into_active_sessions(attendee, actor=changed_by)
    persist_lodging_stay_status(attendee)

    log_retreat_change(
        user=changed_by,
        event=target_group.event,
        action=(
            RetreatChangeLog.Action.CREATE
            if created
            else RetreatChangeLog.Action.UPDATE
        ),
        target_type=RetreatChangeLog.TargetType.ATTENDEE,
        target_id=attendee.id,
        payload_after={
            "group_id": target_group.id,
            "user_id": user.id if user else None,
            "member_role": member_role,
            "source": "home_group_move",
            "from_group_id": old_group_id,
        },
    )
    return attendee


def sync_attendee_from_membership(
    membership: RetreatGroupMembership,
    *,
    changed_by,
) -> RetreatAttendee | None:
    """운영진 멤버십에 맞춰 조원 행을 생성·갱신·이동한다.

    - 소속 없음: 이 조에 attendee 생성 (B1).
    - 소속이 이 조: member_role 을 멤버십에 맞춤.
    - 소속이 다른 조 + 조장/부조장: 소속 유지, 권한만 (겸직).
    - 소속이 다른 조 + 조원: 소속을 이 조로 이동.
    """
    user = membership.user
    group = membership.group
    home = home_attendee_for_user_in_event(user, event_id=group.event_id)

    if home is not None and home.group_id != group.id:
        if home.member_role in _LEADER_ROLES:
            # 겸직: 소속 유지
            return home
        # 조원 → 타조 조장/부조장: 소속 이동
        return move_home_attendee_to_group(
            home=home,
            target_group=group,
            member_role=membership.role,
            changed_by=changed_by,
        )

    if home is not None and home.group_id == group.id:
        if home.member_role != membership.role:
            home.member_role = membership.role
            home.save(update_fields=["member_role", "updated_at"])
            log_retreat_change(
                user=changed_by,
                event=group.event,
                action=RetreatChangeLog.Action.UPDATE,
                target_type=RetreatChangeLog.TargetType.ATTENDEE,
                target_id=home.id,
                payload_after={
                    "group_id": group.id,
                    "user_id": user.id,
                    "member_role": membership.role,
                    "source": "group_membership_sync",
                },
            )
        return home

    # B1: 소속 조 없음 → 이 조에 명단 생성
    attendee = _upsert_attendee_in_group(
        group=group,
        user=user,
        member_role=membership.role,
        changed_by=changed_by,
        source="group_membership_sync",
    )
    consolidate_user_to_event_group(user, group, changed_by=changed_by)
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
    - 계정 연결 + 조원: **이 조** 멤버십만 제거 (다른 조 담당 권한은 유지)
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
            action=(
                RetreatChangeLog.Action.CREATE
                if created
                else RetreatChangeLog.Action.UPDATE
            ),
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
        existing = RetreatGroupMembership.objects.filter(group=group, user=user).first()
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
    # 소속 조 중복만 정리. 다른 조 운영진 멤버십은 유지.
    consolidate_user_to_event_group(user, group, changed_by=changed_by)


def remove_membership_for_attendee(attendee: RetreatAttendee, *, changed_by) -> None:
    """조원 행 삭제 시 같은 집회의 모든 조 운영진 멤버십을 제거한다."""
    if attendee.user_id is None:
        return
    event = attendee.group.event
    memberships = list(
        RetreatGroupMembership.objects.filter(
            user_id=attendee.user_id,
            group__event_id=event.id,
        ).select_related("group")
    )
    for existing in memberships:
        mid = existing.id
        group_id = existing.group_id
        existing.delete()
        log_retreat_change(
            user=changed_by,
            event=event,
            action=RetreatChangeLog.Action.DELETE,
            target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
            target_id=mid,
            payload_before={
                "group_id": group_id,
                "user_id": attendee.user_id,
                "source": "attendee_delete_cascade",
            },
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

    소속 조(이 조의 attendee)를 삭제하면 같은 집회 다른 조 운영진도 cascade.
    """
    group_id = membership.group_id
    user_id = membership.user_id
    if not group_id or not user_id:
        return 0
    removed = 0
    for attendee in list(
        RetreatAttendee.objects.filter(
            group_id=group_id, user_id=user_id
        ).select_related("group", "group__event")
    ):
        attendee_id = attendee.id
        event_id = attendee.group.event_id
        delete_pickups_for_attendee(attendee, changed_by=changed_by)
        # 소속 조원 삭제 시 다른 조 운영진도 정리 (호출 중인 membership 은 admin 이 이어서 삭제).
        for other in list(
            RetreatGroupMembership.objects.filter(
                user_id=user_id,
                group__event_id=event_id,
            ).exclude(group_id=group_id)
        ):
            mid = other.id
            other_group_id = other.group_id
            other.delete()
            log_retreat_change(
                user=changed_by,
                event=event_id,
                action=RetreatChangeLog.Action.DELETE,
                target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
                target_id=mid,
                payload_before={
                    "group_id": other_group_id,
                    "user_id": user_id,
                    "source": "admin_membership_delete_cascade",
                },
            )
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
    """운영진 제거 시 조원 행은 유지하고 역할만 조원으로 내린다.

    담당 조(소속 조가 아닌 조) 운영진 해제는 명단에 영향 없음.
    """
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
