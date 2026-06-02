"""수련회 회장단 명단 관리 API."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.models import (
    RetreatChangeLog,
    RetreatCouncilMembership,
    RetreatEvent,
)
from retreat.serializers import RetreatCouncilMembershipSerializer
from retreat.services.audit import log_retreat_change
from users.permissions import (
    can_access_retreat_tab,
    is_retreat_council,
    is_retreat_staff,
)

User = get_user_model()


def _assert_event_access(user) -> None:
    if not can_access_retreat_tab(user):
        raise PermissionDenied


def _assert_can_view(user, event: RetreatEvent) -> None:
    _assert_event_access(user)
    if not (user.is_superuser or is_retreat_council(user, event) or is_retreat_staff(user, event)):
        raise PermissionDenied("회장단 명단 조회 권한이 없습니다.")


def _assert_can_manage(user, event: RetreatEvent) -> None:
    _assert_event_access(user)
    if not is_retreat_council(user, event):
        raise PermissionDenied("회장단 등록·삭제는 회장단(또는 슈퍼유저)만 가능합니다.")


class RetreatEventCouncilListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        _assert_can_view(request.user, event)
        qs = event.council_memberships.select_related("user").order_by(
            "role", "user__username"
        )
        return Response(RetreatCouncilMembershipSerializer(qs, many=True).data)

    def post(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        _assert_can_manage(request.user, event)
        username = (request.data.get("username") or "").strip()
        user_id = request.data.get("user_id")
        role = (request.data.get("role") or RetreatCouncilMembership.Role.MEMBER).strip()
        note = (request.data.get("note") or "").strip()
        if role not in dict(RetreatCouncilMembership.Role.choices):
            raise ValidationError({"role": "올바르지 않은 역할입니다."})
        target = None
        if user_id:
            target = User.objects.filter(pk=user_id).first()
        elif username:
            target = User.objects.filter(username=username).first()
        if target is None:
            raise ValidationError({"user": "사용자를 찾을 수 없습니다."})
        membership, created = RetreatCouncilMembership.objects.update_or_create(
            event=event,
            user=target,
            defaults={
                "role": role,
                "note": note,
            },
        )
        if created:
            membership.created_by = request.user
            membership.save(update_fields=["created_by"])
        log_retreat_change(
            user=request.user,
            event=event,
            action=RetreatChangeLog.Action.CREATE
            if created
            else RetreatChangeLog.Action.UPDATE,
            target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
            target_id=membership.id,
            payload_after={
                "council": True,
                "user_id": target.id,
                "role": role,
                "note": note,
            },
        )
        return Response(
            RetreatCouncilMembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class RetreatCouncilMembershipDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, event_id: int, membership_id: int) -> RetreatCouncilMembership:
        return get_object_or_404(
            RetreatCouncilMembership.objects.select_related("event", "user"),
            pk=membership_id,
            event_id=event_id,
        )

    def patch(self, request, event_id: int, membership_id: int):
        m = self._get(event_id, membership_id)
        _assert_can_manage(request.user, m.event)
        role = (request.data.get("role") or m.role).strip()
        note = request.data.get("note", m.note)
        if role not in dict(RetreatCouncilMembership.Role.choices):
            raise ValidationError({"role": "올바르지 않은 역할입니다."})
        m.role = role
        m.note = note
        m.save(update_fields=["role", "note"])
        log_retreat_change(
            user=request.user,
            event=m.event,
            action=RetreatChangeLog.Action.UPDATE,
            target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
            target_id=m.id,
            payload_after={"council": True, "role": role, "note": note},
        )
        return Response(RetreatCouncilMembershipSerializer(m).data)

    def delete(self, request, event_id: int, membership_id: int):
        m = self._get(event_id, membership_id)
        _assert_can_manage(request.user, m.event)
        before = {"council": True, "user_id": m.user_id, "role": m.role}
        event = m.event
        mid = m.id
        m.delete()
        log_retreat_change(
            user=request.user,
            event=event,
            action=RetreatChangeLog.Action.DELETE,
            target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
            target_id=mid,
            payload_before=before,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
