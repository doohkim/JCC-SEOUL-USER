"""조 운영진(조장·부조장) CRUD API.

권한:
- 조회: ``get_group_or_403`` (가시 조만)
- 변경: ``assert_can_manage_group_leaders`` (슈퍼유저 / 회장단 / 본인 조 운영진)
- 목사·전도사는 읽기 전용.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.apis._common import assert_can_manage_group_leaders, get_group_or_403
from retreat.models import RetreatChangeLog, RetreatGroupMembership
from retreat.serializers import RetreatGroupMembershipSerializer
from retreat.services.audit import log_retreat_change
from retreat.services.account_retired import (
    assert_user_visible_to,
    visible_user_linked_for,
)
from retreat.services.group_sync import (
    clear_leader_role_on_membership_removed,
    home_attendee_for_user_in_event,
    sync_attendee_from_membership,
)
from retreat.services.staff_roster import assert_can_assign_event_staff

User = get_user_model()


def _resolve_user(payload):
    """payload 에서 user_id / username 으로 사용자 조회."""
    user_id = payload.get("user_id")
    username = (payload.get("username") or "").strip()
    if user_id:
        return User.objects.filter(pk=user_id).first()
    if username:
        return User.objects.filter(username=username).first()
    return None


def _validate_role(value: str) -> str:
    if value not in dict(RetreatGroupMembership.Role.choices):
        raise ValidationError({"role": "올바르지 않은 역할입니다."})
    return value


class RetreatGroupMembershipListCreateView(APIView):
    """조에 등록된 운영진 목록/추가."""

    permission_classes = [IsAuthenticated]

    def get(self, request, group_id: int):
        group = get_group_or_403(request.user, group_id)
        qs = group.memberships.select_related("user", "user__profile").order_by(
            "role", "user__username"
        )
        qs = visible_user_linked_for(request.user, qs, user_prefix="user")
        return Response(RetreatGroupMembershipSerializer(qs, many=True).data)

    def post(self, request, group_id: int):
        group = get_group_or_403(request.user, group_id)
        assert_can_manage_group_leaders(request.user, group)

        target = _resolve_user(request.data)
        if target is None:
            raise ValidationError({"user": "사용자를 찾을 수 없습니다."})
        role = _validate_role(
            (request.data.get("role") or RetreatGroupMembership.Role.LEADER).strip()
        )
        if not RetreatGroupMembership.objects.filter(group=group, user=target).exists():
            try:
                assert_can_assign_event_staff(
                    target, group.event, kind="group", group=group
                )
            except ValueError as exc:
                raise ValidationError({"user": str(exc)}) from exc

        home_before = home_attendee_for_user_in_event(target, event_id=group.event_id)
        prev_group_id = home_before.group_id if home_before else None
        prev_group_name = home_before.group.name if home_before else ""
        membership, created = RetreatGroupMembership.objects.update_or_create(
            group=group,
            user=target,
            defaults={"role": role},
        )
        log_retreat_change(
            user=request.user,
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
                "user_id": target.id,
                "username": target.username,
                "role": role,
            },
        )
        sync_attendee_from_membership(membership, changed_by=request.user)
        data = RetreatGroupMembershipSerializer(membership).data
        if created and prev_group_id is not None and prev_group_id != group.id:
            home_after = home_attendee_for_user_in_event(
                target, event_id=group.event_id
            )
            role_label = membership.get_role_display()
            if home_after is not None and home_after.group_id == group.id:
                data["moved_home_group"] = True
                data["message"] = (
                    f"{prev_group_name}에서 {group.name}으로 소속을 옮기고 "
                    f"{role_label}으로 등록했습니다."
                )
            else:
                data["kept_home_group"] = True
                data["message"] = (
                    f"{prev_group_name} 소속을 유지한 채 "
                    f"{group.name} {role_label} 권한을 추가했습니다."
                )
        return Response(
            data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class RetreatGroupMembershipDetailView(APIView):
    """조 운영진 단건 PATCH/DELETE."""

    permission_classes = [IsAuthenticated]

    def _get(self, membership_id: int) -> RetreatGroupMembership:
        return get_object_or_404(
            RetreatGroupMembership.objects.select_related(
                "user", "group", "group__event"
            ),
            pk=membership_id,
        )

    def patch(self, request, membership_id: int):
        membership = self._get(membership_id)
        assert_user_visible_to(request.user, membership.user)
        assert_can_manage_group_leaders(request.user, membership.group)
        role = _validate_role((request.data.get("role") or membership.role).strip())
        before = {
            "group_id": membership.group_id,
            "user_id": membership.user_id,
            "role": membership.role,
        }
        membership.role = role
        membership.save(update_fields=["role"])
        sync_attendee_from_membership(membership, changed_by=request.user)
        log_retreat_change(
            user=request.user,
            event=membership.group.event,
            action=RetreatChangeLog.Action.UPDATE,
            target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
            target_id=membership.id,
            payload_before=before,
            payload_after={
                "group_id": membership.group_id,
                "user_id": membership.user_id,
                "username": membership.user.username,
                "role": membership.role,
            },
        )
        return Response(RetreatGroupMembershipSerializer(membership).data)

    def delete(self, request, membership_id: int):
        membership = self._get(membership_id)
        assert_user_visible_to(request.user, membership.user)
        assert_can_manage_group_leaders(request.user, membership.group)
        before = {
            "group_id": membership.group_id,
            "user_id": membership.user_id,
            "username": membership.user.username,
            "role": membership.role,
        }
        event = membership.group.event
        mid = membership.id
        clear_leader_role_on_membership_removed(membership, changed_by=request.user)
        membership.delete()
        from retreat.services.staff_application import (
            delete_staff_application_if_unassigned,
        )

        delete_staff_application_if_unassigned(
            membership.user, event, actor=request.user
        )
        log_retreat_change(
            user=request.user,
            event=event,
            action=RetreatChangeLog.Action.DELETE,
            target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
            target_id=mid,
            payload_before=before,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
