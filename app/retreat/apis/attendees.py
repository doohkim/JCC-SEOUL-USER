"""조원 CRUD API."""

from __future__ import annotations

from copy import deepcopy

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.apis._common import (
    assert_can_mutate_group,
    get_group_or_403,
    user_can_edit_attendee_timestamps,
)
from retreat.models import RetreatAttendee, RetreatChangeLog
from retreat.serializers import RetreatAttendeeSerializer
from retreat.services.audit import log_retreat_change, serialize_model_fields
from retreat.services.check_in_stamps import apply_attendee_stamp_from_payload
from retreat.services.enrollment import enroll_attendee_into_active_sessions
from retreat.services.lodging import assert_room_can_accept

_ATTENDEE_FIELDS = [
    "id",
    "group_id",
    "name",
    "phone",
    "gender",
    "memo",
    "check_in_status",
    "expected_check_in_at",
    "expected_check_out_at",
    "checked_in_at",
    "checked_out_at",
    "lodging_room_id",
    "sort_order",
]


def _payload_without_timestamps_if_forbidden(user, group: RetreatGroup, data):
    payload = deepcopy(dict(data))
    if not user_can_edit_attendee_timestamps(user, group):
        payload.pop("checked_in_at", None)
        payload.pop("checked_out_at", None)
    return payload


def _manual_timestamps_from_payload(data) -> tuple:
    return data.get("checked_in_at"), data.get("checked_out_at")


class RetreatGroupAttendeesView(APIView):
    """조원 목록 / 추가.

    - GET: 조원 목록
    - POST: 조원 추가
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, group_id: int):
        group = get_group_or_403(request.user, group_id)
        attendees = group.attendees.all().order_by("sort_order", "name", "id")
        return Response(RetreatAttendeeSerializer(attendees, many=True).data)

    def post(self, request, group_id: int):
        group = get_group_or_403(request.user, group_id)
        assert_can_mutate_group(request.user, group)
        payload = _payload_without_timestamps_if_forbidden(
            request.user, group, request.data
        )
        data = dict(payload)
        data["group"] = group.id
        ser = RetreatAttendeeSerializer(data=data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        target_room = ser.validated_data.get("lodging_room")
        if target_room is not None:
            tmp = RetreatAttendee(
                group=group,
                gender=ser.validated_data.get("gender", ""),
                lodging_room=target_room,
            )
            assert_room_can_accept(target_room, tmp)
        attendee = ser.save()
        stamp_fields = ["updated_at"]
        if attendee.check_in_status == RetreatAttendee.CheckInStatus.CHECKED_IN:
            attendee.checked_in_at = timezone.now()
            stamp_fields.append("checked_in_at")
        elif attendee.check_in_status == RetreatAttendee.CheckInStatus.CHECKED_OUT:
            attendee.checked_out_at = timezone.now()
            stamp_fields.append("checked_out_at")
        if len(stamp_fields) > 1:
            attendee.save(update_fields=stamp_fields)
        enroll_attendee_into_active_sessions(attendee, actor=request.user)
        log_retreat_change(
            user=request.user,
            event=group.event,
            action=RetreatChangeLog.Action.CREATE,
            target_type=RetreatChangeLog.TargetType.ATTENDEE,
            target_id=attendee.id,
            payload_after=serialize_model_fields(attendee, _ATTENDEE_FIELDS),
        )
        return Response(
            RetreatAttendeeSerializer(attendee).data, status=status.HTTP_201_CREATED
        )


class RetreatAttendeeDetailView(APIView):
    """조원 수정 / 삭제 (PATCH / DELETE)."""

    permission_classes = [IsAuthenticated]

    def _get(self, request, attendee_id: int) -> RetreatAttendee:
        attendee = get_object_or_404(RetreatAttendee, pk=attendee_id)
        get_group_or_403(request.user, attendee.group_id)
        return attendee

    def get(self, request, attendee_id: int):
        attendee = self._get(request, attendee_id)
        return Response(RetreatAttendeeSerializer(attendee).data)

    def patch(self, request, attendee_id: int):
        attendee = self._get(request, attendee_id)
        group = attendee.group
        assert_can_mutate_group(request.user, group)
        before = serialize_model_fields(attendee, _ATTENDEE_FIELDS)
        previous_status = attendee.check_in_status
        payload = _payload_without_timestamps_if_forbidden(
            request.user, group, request.data
        )
        ser = RetreatAttendeeSerializer(attendee, data=payload, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        if "lodging_room" in ser.validated_data:
            target_room = ser.validated_data["lodging_room"]
            if target_room is not None:
                tmp = attendee
                tmp.lodging_room = target_room
                assert_room_can_accept(target_room, tmp)
        attendee = ser.save()
        manual_in = ser.validated_data.get("checked_in_at")
        manual_out = ser.validated_data.get("checked_out_at")
        apply_attendee_stamp_from_payload(
            attendee,
            previous_status=previous_status,
            validated_data=ser.validated_data,
            manual_checked_in_at=manual_in,
            manual_checked_out_at=manual_out,
        )
        attendee.save(
            update_fields=[
                "check_in_status",
                "checked_in_at",
                "checked_out_at",
                "updated_at",
            ]
        )
        log_retreat_change(
            user=request.user,
            event=group.event,
            action=RetreatChangeLog.Action.UPDATE,
            target_type=RetreatChangeLog.TargetType.ATTENDEE,
            target_id=attendee.id,
            payload_before=before,
            payload_after=serialize_model_fields(attendee, _ATTENDEE_FIELDS),
        )
        return Response(RetreatAttendeeSerializer(attendee).data)

    def delete(self, request, attendee_id: int):
        attendee = self._get(request, attendee_id)
        assert_can_mutate_group(request.user, attendee.group)
        before = serialize_model_fields(attendee, _ATTENDEE_FIELDS)
        event = attendee.group.event
        aid = attendee.id
        attendee.delete()
        log_retreat_change(
            user=request.user,
            event=event,
            action=RetreatChangeLog.Action.DELETE,
            target_type=RetreatChangeLog.TargetType.ATTENDEE,
            target_id=aid,
            payload_before=before,
            payload_after=None,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
