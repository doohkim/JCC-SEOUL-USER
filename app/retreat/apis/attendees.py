"""조원 CRUD API."""

from __future__ import annotations

from copy import deepcopy

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.apis._common import (
    _ATTENDEE_DETAIL_PATCH_KEYS,
    _CHECK_IN_STATUS_KEYS,
    assert_can_change_check_in_status,
    assert_can_delete_attendee,
    assert_can_edit_attendee_details,
    assert_can_link_attendee_user,
    assert_check_in_status_transition,
    get_group_or_403,
    profile_locked_patch_keys_for,
    user_can_edit_attendee_timestamps,
)
from retreat.services.check_in_stamps import (
    apply_attendee_stamp_from_payload,
    is_attendee_profile_locked,
)
from retreat.services.enrollment import enroll_attendee_into_active_sessions
from retreat.services.group_sync import (
    remove_membership_for_attendee,
    sync_membership_from_attendee,
)
from users.permissions import can_change_retreat_check_in, can_link_attendee_user
from retreat.models import RetreatAttendee, RetreatChangeLog, RetreatGroup
from retreat.serializers import RetreatAttendeeSerializer
from retreat.services.audit import log_retreat_change, serialize_model_fields
from retreat.services.lodging import assert_room_can_accept
from retreat.services.lodging_stay import persist_lodging_stay_status, sync_lodging_stay_status
from retreat.services.participation import apply_participation_change
from retreat.services.pickup_attendee import (
    delete_pickups_for_attendee,
    pickups_for_attendee,
    serialize_pickup_for_attendee_preview,
)

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
    "lodging_stay_status",
    "participation_status",
    "sort_order",
]


def _sanitize_attendee_payload(user, group: RetreatGroup, data):
    """권한 없는 키는 제거한다."""
    payload = deepcopy(dict(data))
    if not can_change_retreat_check_in(user, group.event):
        payload.pop("check_in_status", None)
        payload.pop("checked_in_at", None)
        payload.pop("checked_out_at", None)
    elif not user_can_edit_attendee_timestamps(user, group):
        payload.pop("checked_in_at", None)
        payload.pop("checked_out_at", None)
    if not can_link_attendee_user(user, group.event):
        payload.pop("user", None)
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
        assert_can_edit_attendee_details(request.user, group)
        raw_status = request.data.get("check_in_status") or RetreatAttendee.CheckInStatus.PENDING
        if raw_status != RetreatAttendee.CheckInStatus.PENDING:
            assert_can_change_check_in_status(request.user, group)
        payload = _sanitize_attendee_payload(request.user, group, request.data)
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
        attendee = ser.save(created_by=request.user)
        stamp_fields = ["updated_at"]
        if attendee.check_in_status == RetreatAttendee.CheckInStatus.CHECKED_IN:
            attendee.checked_in_at = timezone.now()
            stamp_fields.append("checked_in_at")
        elif attendee.check_in_status == RetreatAttendee.CheckInStatus.CHECKED_OUT:
            attendee.checked_out_at = timezone.now()
            stamp_fields.append("checked_out_at")
        if len(stamp_fields) > 1:
            attendee.save(update_fields=stamp_fields)
        persist_lodging_stay_status(attendee)
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
        attendee = get_object_or_404(
            RetreatAttendee.objects.select_related("group", "group__event"),
            pk=attendee_id,
        )
        get_group_or_403(request.user, attendee.group_id)
        return attendee

    def get(self, request, attendee_id: int):
        attendee = self._get(request, attendee_id)
        data = RetreatAttendeeSerializer(attendee).data
        if (request.query_params.get("with_pickups") or "").strip() in (
            "1",
            "true",
            "yes",
        ):
            data["linked_pickups"] = [
                serialize_pickup_for_attendee_preview(p)
                for p in pickups_for_attendee(attendee)
            ]
        return Response(data)

    def patch(self, request, attendee_id: int):
        attendee = self._get(request, attendee_id)
        group = attendee.group
        raw_keys = set(request.data.keys())
        if raw_keys & _CHECK_IN_STATUS_KEYS:
            assert_can_change_check_in_status(request.user, group)
        if "user" in raw_keys:
            assert_can_link_attendee_user(request.user, group)
        payload = _sanitize_attendee_payload(request.user, group, request.data)
        keys = set(payload.keys())
        detail_keys = keys & _ATTENDEE_DETAIL_PATCH_KEYS
        profile_keys = keys & profile_locked_patch_keys_for(
            request.user, group, attendee
        )
        if is_attendee_profile_locked(attendee) and profile_keys:
            raise PermissionDenied("퇴실 상태 조원의 정보는 수정할 수 없습니다.")
        if detail_keys:
            assert_can_edit_attendee_details(request.user, group)
        elif keys:
            assert_can_edit_attendee_details(request.user, group)

        if "check_in_status" in payload:
            assert_check_in_status_transition(
                request.user,
                group,
                previous=attendee.check_in_status,
                new=str(payload["check_in_status"]),
            )

        before = serialize_model_fields(attendee, _ATTENDEE_FIELDS)
        previous_status = attendee.check_in_status
        previous_participation = attendee.participation_status
        ser = RetreatAttendeeSerializer(
            attendee,
            data=payload,
            partial=True,
            context={"user": request.user, "group": group},
        )
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
                    participation_status=ser.validated_data.get(
                        "participation_status", attendee.participation_status
                    ),
                )
                assert_room_can_accept(target_room, tmp)
        attendee = ser.save()
        extra_fields = apply_participation_change(
            attendee,
            previous=previous_participation,
            new=attendee.participation_status,
            actor=request.user,
        )
        if extra_fields:
            attendee.save(update_fields=[*extra_fields, "updated_at"])
        manual_in = ser.validated_data.get("checked_in_at")
        manual_out = ser.validated_data.get("checked_out_at")
        apply_attendee_stamp_from_payload(
            attendee,
            previous_status=previous_status,
            validated_data=ser.validated_data,
            manual_checked_in_at=manual_in,
            manual_checked_out_at=manual_out,
        )
        sync_lodging_stay_status(attendee)
        attendee.save(
            update_fields=[
                "check_in_status",
                "checked_in_at",
                "checked_out_at",
                "lodging_stay_status",
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
        assert_can_delete_attendee(request.user, attendee.group, attendee=attendee)
        before = serialize_model_fields(attendee, _ATTENDEE_FIELDS)
        event = attendee.group.event
        aid = attendee.id
        deleted_pickups = delete_pickups_for_attendee(attendee, changed_by=request.user)
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
        return Response(
            {"deleted_pickup_count": deleted_pickups},
            status=status.HTTP_200_OK,
        )
