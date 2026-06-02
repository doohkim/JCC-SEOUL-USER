"""온보딩 승인 시 수련회 멤버십 연동."""

from __future__ import annotations

from retreat.models import RetreatChangeLog, RetreatGroup, RetreatGroupMembership
from retreat.services.audit import log_retreat_change


RETREAT_ROLE_LABELS = {
    "": "참가자",
    "participant": "참가자",
    "leader": "조장",
    "vice_leader": "부조장",
}


def apply_retreat_membership_on_approval(
    *,
    user,
    profile,
    retreat_group_id: str | None,
    retreat_role: str | None,
    changed_by,
) -> None:
    """승인 시 수련회 조 운영진 멤버십 생성(조장·부조장만)."""
    if not profile.requested_retreat_participation:
        return
    role = (retreat_role or profile.requested_retreat_role or "").strip()
    if role not in (
        RetreatGroupMembership.Role.LEADER,
        RetreatGroupMembership.Role.VICE_LEADER,
    ):
        return
    if not retreat_group_id or not str(retreat_group_id).isdigit():
        return

    group = RetreatGroup.objects.filter(pk=int(retreat_group_id)).first()
    if group is None:
        return
    if profile.requested_retreat_event_id and group.event_id != profile.requested_retreat_event_id:
        return

    membership, created = RetreatGroupMembership.objects.update_or_create(
        user=profile.user,
        group=group,
        defaults={"role": role},
    )
    log_retreat_change(
        user=changed_by,
        event=group.event,
        action=RetreatChangeLog.Action.CREATE
        if created
        else RetreatChangeLog.Action.UPDATE,
        target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
        target_id=membership.id,
        payload_before=None if created else {"role": role},
        payload_after={"user_id": profile.user_id, "group_id": group.id, "role": role},
    )
