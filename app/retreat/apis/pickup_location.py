"""수련회 탑승장소(픽업 위치) 목록 관리 API — 회장단·슈퍼유저 전용."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.models import RetreatChangeLog, RetreatEvent, RetreatPickupLocation
from retreat.serializers import RetreatPickupLocationSerializer
from retreat.services.audit import log_retreat_change
from users.permissions import can_manage_retreat_pickup_location


def _assert_can_manage_location(user, event: RetreatEvent) -> None:
    if not can_manage_retreat_pickup_location(user, event):
        raise PermissionDenied("탑승장소 목록을 관리할 권한이 없습니다.")


def _serialize_location(loc: RetreatPickupLocation) -> dict:
    return {
        "id": loc.id,
        "event_id": loc.event_id,
        "name": loc.name,
        "sort_order": loc.sort_order,
    }


class RetreatEventPickupLocationListCreateView(APIView):
    """집회별 탑승장소 목록 조회·추가 (회장단·슈퍼유저)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        _assert_can_manage_location(request.user, event)
        qs = event.pickup_locations.order_by("sort_order", "name", "id")
        return Response(RetreatPickupLocationSerializer(qs, many=True).data)

    def post(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        _assert_can_manage_location(request.user, event)

        name = (request.data.get("name") or "").strip()
        sort_order = request.data.get("sort_order", 0)

        if not name:
            raise ValidationError({"name": "탑승장소 이름을 입력하세요."})

        try:
            sort_order = int(sort_order)
        except (TypeError, ValueError):
            sort_order = 0
        if sort_order < 0:
            sort_order = 0

        if RetreatPickupLocation.objects.filter(event=event, name=name).exists():
            raise ValidationError({"name": "동일한 탑승장소가 이미 있습니다."})

        loc = RetreatPickupLocation.objects.create(
            event=event,
            name=name,
            sort_order=sort_order,
            created_by=request.user,
        )
        log_retreat_change(
            user=request.user,
            event=event,
            action=RetreatChangeLog.Action.CREATE,
            target_type=RetreatChangeLog.TargetType.PICKUP_LOCATION,
            target_id=loc.id,
            payload_after=_serialize_location(loc),
        )
        return Response(
            RetreatPickupLocationSerializer(loc).data,
            status=status.HTTP_201_CREATED,
        )


class RetreatPickupLocationDetailView(APIView):
    """탑승장소 수정·삭제 (회장단·슈퍼유저)."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, location_id: int):
        loc = get_object_or_404(
            RetreatPickupLocation.objects.select_related("event"),
            pk=location_id,
        )
        _assert_can_manage_location(request.user, loc.event)
        before = _serialize_location(loc)

        data = request.data
        errors: dict[str, str] = {}
        update_fields: list[str] = []

        if "name" in data:
            name = (data.get("name") or "").strip()
            if not name:
                errors["name"] = "탑승장소 이름을 입력하세요."
            else:
                loc.name = name
                update_fields.append("name")

        if "sort_order" in data:
            try:
                loc.sort_order = max(0, int(data.get("sort_order")))
            except (TypeError, ValueError):
                errors["sort_order"] = "정렬 값이 올바르지 않습니다."
            else:
                update_fields.append("sort_order")

        if errors:
            raise ValidationError(errors)

        if update_fields:
            if (
                "name" in update_fields
                and RetreatPickupLocation.objects.filter(
                    event=loc.event,
                    name=loc.name,
                )
                .exclude(pk=loc.pk)
                .exists()
            ):
                raise ValidationError({"name": "동일한 탑승장소가 이미 있습니다."})
            update_fields.append("updated_at")
            loc.save(update_fields=sorted(set(update_fields)))

        log_retreat_change(
            user=request.user,
            event=loc.event,
            action=RetreatChangeLog.Action.UPDATE,
            target_type=RetreatChangeLog.TargetType.PICKUP_LOCATION,
            target_id=loc.id,
            payload_before=before,
            payload_after=_serialize_location(loc),
        )
        return Response(RetreatPickupLocationSerializer(loc).data)

    def delete(self, request, location_id: int):
        loc = get_object_or_404(
            RetreatPickupLocation.objects.select_related("event"),
            pk=location_id,
        )
        _assert_can_manage_location(request.user, loc.event)
        before = _serialize_location(loc)
        event = loc.event
        lid = loc.id
        loc.delete()
        log_retreat_change(
            user=request.user,
            event=event,
            action=RetreatChangeLog.Action.DELETE,
            target_type=RetreatChangeLog.TargetType.PICKUP_LOCATION,
            target_id=lid,
            payload_before=before,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
