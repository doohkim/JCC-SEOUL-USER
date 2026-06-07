"""행사·그룹 목록 API."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.apis._common import assert_can_add_group
from retreat.models import (
    RetreatChangeLog,
    RetreatEvent,
    RetreatGroup,
    RetreatGroupMembership,
)
from retreat.serializers import RetreatEventSerializer, RetreatGroupSerializer
from retreat.services.audit import log_retreat_change
from users.models import Division
from users.permissions import visible_retreat_groups_for

User = get_user_model()


class RetreatEventListView(APIView):
    """현재 사용자에게 노출 가능한 활성 행사 목록.

    - 활성 행사 중, 본인이 1개 이상 그룹을 볼 수 있거나 슈퍼유저인 행사만.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        events = RetreatEvent.objects.filter(is_active=True).prefetch_related("sessions")
        if not request.user.is_superuser:
            visible = []
            for ev in events:
                if visible_retreat_groups_for(request.user, ev).exists():
                    visible.append(ev)
            events = visible
        return Response(
            RetreatEventSerializer(
                events,
                many=True,
                context={"request": request},
            ).data
        )


class RetreatEventGroupListView(APIView):
    """특정 행사에서 본인이 볼 수 있는 조 목록."""

    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        groups = (
            visible_retreat_groups_for(request.user, event)
            .select_related("region", "division")
            .prefetch_related("memberships__user")
            .annotate(attendee_count=Count("attendees", distinct=True))
        )
        return Response(RetreatGroupSerializer(groups, many=True).data)

    def post(self, request, event_id: int):
        """행사에 조 추가 (회장단·슈퍼유저)."""
        event = get_object_or_404(RetreatEvent, pk=event_id)
        assert_can_add_group(request.user, event)

        region_id = request.data.get("region")
        division_id = request.data.get("division")
        name = (request.data.get("name") or "").strip()
        order = request.data.get("order", 0)
        leaders = request.data.get("leaders") or []

        if not name:
            raise ValidationError({"name": "조 이름은 필수입니다."})
        if not region_id or not division_id:
            raise ValidationError({"region": "지역과 부서를 선택하세요."})

        division = get_object_or_404(
            Division.objects.select_related("region"), pk=int(division_id)
        )
        if int(region_id) != division.region_id:
            raise ValidationError(
                {"division": "선택한 지역에 속한 부서가 아닙니다."}
            )

        if RetreatGroup.objects.filter(event=event, name=name).exists():
            raise ValidationError(
                {"name": "이 행사에 이미 같은 이름의 조가 있습니다."}
            )

        group = RetreatGroup.objects.create(
            event=event,
            region_id=int(region_id),
            division=division,
            name=name,
            order=int(order or 0),
        )
        log_retreat_change(
            user=request.user,
            event=event,
            action=RetreatChangeLog.Action.CREATE,
            target_type=RetreatChangeLog.TargetType.GROUP,
            target_id=group.id,
            payload_after={
                "event_id": event.id,
                "region_id": group.region_id,
                "division_id": group.division_id,
                "name": group.name,
                "order": group.order,
            },
        )

        for entry in leaders:
            if not isinstance(entry, dict):
                continue
            user_id = entry.get("user_id")
            role = (entry.get("role") or RetreatGroupMembership.Role.LEADER).strip()
            if role not in dict(RetreatGroupMembership.Role.choices):
                continue
            if not user_id:
                continue
            target = User.objects.filter(pk=user_id, is_active=True).first()
            if target is None:
                continue
            membership, created = RetreatGroupMembership.objects.update_or_create(
                group=group,
                user=target,
                defaults={"role": role},
            )
            log_retreat_change(
                user=request.user,
                event=event,
                action=RetreatChangeLog.Action.CREATE
                if created
                else RetreatChangeLog.Action.UPDATE,
                target_type=RetreatChangeLog.TargetType.GROUP_MEMBERSHIP,
                target_id=membership.id,
                payload_after={
                    "group_id": group.id,
                    "user_id": target.id,
                    "role": role,
                },
            )

        group = (
            RetreatGroup.objects.filter(pk=group.pk)
            .select_related("region", "division")
            .prefetch_related("memberships__user")
            .annotate(attendee_count=Count("attendees", distinct=True))
            .first()
        )
        return Response(
            RetreatGroupSerializer(group).data,
            status=status.HTTP_201_CREATED,
        )
