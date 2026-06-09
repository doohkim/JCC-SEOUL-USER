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
    _PROFILE_PATCH_KEYS,
    assert_can_delete_attendee,
    assert_can_edit_attendee_details,
    assert_can_mutate_group,
    assert_check_in_status_transition,
    get_group_or_403,
    user_can_edit_attendee_details,
    user_can_edit_attendee_timestamps,
)
from retreat.models import RetreatAttendee, RetreatChangeLog, RetreatGroup
from retreat.serializers import RetreatAttendeeSerializer
from retreat.services.audit import log_retreat_change, serialize_model_fields
from retreat.services.check_in_stamps import apply_attendee_stamp_from_payload
from retreat.services.enrollment import enroll_attendee_into_active_sessions
from retreat.services.group_sync import (
    remove_membership_for_attendee,
    sync_membership_from_attendee,
)
from retreat.services.lodging import assert_room_can_accept

_ATTENDEE_FIELDS = [
    "id",
    "group_id",
    "user_id",
    "member_role",
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
        # 계정 연결·역할(조장/부조장) 부여는 회장단·staff·슈퍼만.
        role = (payload.get("member_role") or "").strip()
        if payload.get("user") or role in (
            RetreatAttendee.MemberRole.LEADER,
            RetreatAttendee.MemberRole.VICE_LEADER,
        ):
            assert_can_edit_attendee_details(request.user, group)
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
        if attendee.user_id:
            sync_membership_from_attendee(attendee, changed_by=request.user)
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
        payload = _payload_without_timestamps_if_forbidden(
            request.user, group, request.data
        )
        keys = set(payload.keys())
        profile_keys = keys & _PROFILE_PATCH_KEYS
        status_keys = keys & {"check_in_status", "checked_in_at", "checked_out_at"}
        expected_keys = keys & {"expected_check_in_at", "expected_check_out_at"}
        lodging_only = keys <= {"lodging_room"} and "lodging_room" in keys

        if profile_keys:
            assert_can_edit_attendee_details(request.user, group)
        elif status_keys or expected_keys or lodging_only:
            assert_can_mutate_group(request.user, group)
        else:
            assert_can_mutate_group(request.user, group)

        if "check_in_status" in payload:
            assert_check_in_status_transition(
                request.user,
                group,
                previous=attendee.check_in_status,
                new=str(payload["check_in_status"]),
            )
        elif profile_keys and not user_can_edit_attendee_details(request.user, group):
            assert_can_edit_attendee_details(request.user, group)

        before = serialize_model_fields(attendee, _ATTENDEE_FIELDS)
        previous_status = attendee.check_in_status
        ser = RetreatAttendeeSerializer(attendee, data=payload, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        if "lodging_room" in ser.validated_data or "gender" in ser.validated_data:
            target_room = ser.validated_data.get("lodging_room", attendee.lodging_room)
            if target_room is not None:
                target_gender = ser.validated_data.get("gender", attendee.gender)
                tmp = RetreatAttendee(
                    id=attendee.id,
                    group=group,
                    gender=target_gender,
                    lodging_room=target_room,
                )
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
        if "member_role" in payload or "user" in payload:
            sync_membership_from_attendee(attendee, changed_by=request.user)
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
        assert_can_delete_attendee(request.user, attendee.group)
        before = serialize_model_fields(attendee, _ATTENDEE_FIELDS)
        event = attendee.group.event
        aid = attendee.id
        remove_membership_for_attendee(attendee, changed_by=request.user)
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
