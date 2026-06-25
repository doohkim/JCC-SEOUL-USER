"""숙소·호실 CRUD API."""

from __future__ import annotations

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.apis._common import (
    assert_can_manage_lodging,
    assert_can_view_lodging,
)
from retreat.models import (
    Lodging,
    LodgingRoom,
    RetreatAttendee,
    RetreatEvent,
)
from retreat.serializers import LodgingRoomSerializer, LodgingSerializer


def _lodgings_with_rooms(event: RetreatEvent):
    """rooms 와 각 room 의 attendees 를 prefetch 한 lodgings queryset."""
    rooms_qs = LodgingRoom.objects.prefetch_related(
        Prefetch(
            "attendees",
            queryset=RetreatAttendee.objects.select_related("group").order_by(
                "name", "id"
            ),
        )
    ).order_by("sort_order", "number", "id")
    return (
        Lodging.objects.filter(event=event)
        .prefetch_related(Prefetch("rooms", queryset=rooms_qs))
        .order_by("sort_order", "name", "id")
    )


class RetreatEventLodgingsView(APIView):
    """집회별 숙소 목록 / 추가."""

    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        assert_can_view_lodging(request.user, event)
        lodgings = _lodgings_with_rooms(event)
        return Response(LodgingSerializer(lodgings, many=True).data)

    def post(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        assert_can_manage_lodging(request.user, event)
        ser = LodgingSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        lodging = ser.save(event=event)
        return Response(
            LodgingSerializer(lodging).data, status=status.HTTP_201_CREATED
        )


class RetreatLodgingDetailView(APIView):
    """숙소 수정 / 삭제."""

    permission_classes = [IsAuthenticated]

    def _get(self, request, lodging_id: int) -> Lodging:
        lodging = get_object_or_404(
            Lodging.objects.select_related("event"), pk=lodging_id
        )
        return lodging

    def get(self, request, lodging_id: int):
        lodging = self._get(request, lodging_id)
        assert_can_view_lodging(request.user, lodging.event)
        return Response(LodgingSerializer(lodging).data)

    def patch(self, request, lodging_id: int):
        lodging = self._get(request, lodging_id)
        assert_can_manage_lodging(request.user, lodging.event)
        ser = LodgingSerializer(lodging, data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        ser.save()
        return Response(LodgingSerializer(lodging).data)

    def delete(self, request, lodging_id: int):
        lodging = self._get(request, lodging_id)
        assert_can_manage_lodging(request.user, lodging.event)
        lodging.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RetreatLodgingRoomsView(APIView):
    """숙소 내 호실 목록 / 추가."""

    permission_classes = [IsAuthenticated]

    def get(self, request, lodging_id: int):
        lodging = get_object_or_404(
            Lodging.objects.select_related("event"), pk=lodging_id
        )
        assert_can_view_lodging(request.user, lodging.event)
        rooms = lodging.rooms.all().order_by("sort_order", "number", "id")
        return Response(LodgingRoomSerializer(rooms, many=True).data)

    def post(self, request, lodging_id: int):
        lodging = get_object_or_404(
            Lodging.objects.select_related("event"), pk=lodging_id
        )
        assert_can_manage_lodging(request.user, lodging.event)
        ser = LodgingRoomSerializer(data={**request.data, "lodging": lodging.id})
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        room = ser.save()
        return Response(
            LodgingRoomSerializer(room).data, status=status.HTTP_201_CREATED
        )


class RetreatLodgingRoomDetailView(APIView):
    """호실 수정 / 삭제."""

    permission_classes = [IsAuthenticated]

    def _get(self, request, room_id: int) -> LodgingRoom:
        return get_object_or_404(
            LodgingRoom.objects.select_related("lodging", "lodging__event"),
            pk=room_id,
        )

    def get(self, request, room_id: int):
        room = self._get(request, room_id)
        assert_can_view_lodging(request.user, room.lodging.event)
        return Response(LodgingRoomSerializer(room).data)

    def patch(self, request, room_id: int):
        room = self._get(request, room_id)
        assert_can_manage_lodging(request.user, room.lodging.event)
        ser = LodgingRoomSerializer(room, data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        ser.save()
        return Response(LodgingRoomSerializer(room).data)

    def delete(self, request, room_id: int):
        room = self._get(request, room_id)
        assert_can_manage_lodging(request.user, room.lodging.event)
        room.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
