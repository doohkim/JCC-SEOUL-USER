"""조원 CRUD API."""

from __future__ import annotations

from copy import deepcopy

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.apis._common import (
    _ATTENDEE_DETAIL_PATCH_KEYS,
    _CHECK_IN_STATUS_KEYS,
    assert_can_change_check_in_status,
    assert_can_delete_attendee,
    assert_can_edit_attendee_details,
    assert_check_in_status_transition,
    get_group_or_403,
    profile_locked_patch_keys_for,
    user_can_edit_attendee_timestamps,
)
from retreat.services.check_in_stamps import (
    apply_attendee_stamp_from_payload,
    is_attendee_profile_locked,
)
from retreat.services.attendee_ordering import order_attendees_for_member_list
from retreat.services.enrollment import enroll_attendee_into_active_sessions
from retreat.services.group_sync import (
    home_attendee_for_user_in_event,
    remove_membership_for_attendee,
    sync_membership_from_attendee,
)
from users.permissions import can_change_retreat_check_in, can_link_attendee_user
from retreat.models import (
    RetreatAttendee,
    RetreatChangeLog,
    RetreatGroup,
    RetreatGroupMembership,
)
from retreat.serializers import RetreatAttendeeSerializer
from retreat.services.audit import log_retreat_change, serialize_model_fields
from retreat.services.lodging import assert_room_can_accept
from retreat.services.lodging_stay import (
    persist_lodging_stay_status,
    sync_lodging_stay_status,
)
from retreat.services.participation import apply_participation_change
from retreat.services.account_retired import (
    assert_attendee_visible_to,
    visible_attendees_for,
)
from retreat.services.pickup_attendee import (
    delete_pickups_for_attendee,
    pickups_for_attendee,
    serialize_pickup_for_attendee_preview,
)

_LEADER_MEMBER_ROLES = frozenset(
    {
        RetreatAttendee.MemberRole.LEADER,
        RetreatAttendee.MemberRole.VICE_LEADER,
        RetreatAttendee.MemberRole.TEACHER,
    }
)


def _assert_home_role_upgrade_allowed(attendee: RetreatAttendee, new_role: str) -> None:
    """다른 조 조장/부조장이면 소속 조 명단에서 조장·부조장 승격을 막는다."""
    if new_role not in _LEADER_MEMBER_ROLES:
        return
    if attendee.member_role in _LEADER_MEMBER_ROLES:
        return
    user_id = attendee.user_id
    if not user_id:
        return
    if (
        RetreatGroupMembership.objects.filter(
            user_id=user_id,
            group__event_id=attendee.group.event_id,
        )
        .exclude(group_id=attendee.group_id)
        .exists()
    ):
        raise ValidationError(
            {
                "member_role": (
                    "이미 다른 조 조장·부조장·선생님입니다. "
                    "소속 조 역할은 조원 수정이 아니라 관리 > 조 운영진에서 처리하세요."
                )
            }
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
    "check_in_status_manually_set",
    "expected_check_in_at",
    "expected_check_out_at",
    "checked_in_at",
    "checked_out_at",
    "lodging_room_id",
    "lodging_stay_status",
    "participation_status",
    "sort_order",
]


def _assert_user_home_group_allows(
    *,
    user,
    group: RetreatGroup,
    exclude_attendee_id: int | None = None,
) -> None:
    """집회당 계정 ↔ 조원 행은 1:1.

    같은 조·다른 조 모두, 이미 다른 조원 행에 연동된 계정은 추가/연동을 막는다.
    (조 운영진 권한 ``RetreatGroupMembership`` 복수 배정과는 별개.)
    """
    if user is None or not getattr(user, "pk", None):
        return
    home = home_attendee_for_user_in_event(user, event_id=group.event_id)
    if home is None:
        return
    if exclude_attendee_id is not None and home.id == exclude_attendee_id:
        return
    if home.group_id == group.id:
        raise ValidationError(
            {
                "user": (
                    f"이미 이 집회 명단({home.group.name} · {home.name})에 "
                    f"연동된 계정입니다. 계정당 조원은 1명만 연결할 수 있습니다."
                )
            }
        )
    raise ValidationError(
        {
            "user": (
                f"이미 {home.group.name} 소속입니다. "
                f"{group.name}에는 관리 > 조 운영진에서 조장·부조장·선생님 권한만 추가하거나, "
                f"소속 조를 이동하세요."
            )
        }
    )


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
        attendees = order_attendees_for_member_list(
            visible_attendees_for(request.user, group.attendees.all())
        )
        return Response(RetreatAttendeeSerializer(attendees, many=True).data)

    def post(self, request, group_id: int):
        group = get_group_or_403(request.user, group_id)
        assert_can_edit_attendee_details(request.user, group)
        raw_status = (
            request.data.get("check_in_status") or RetreatAttendee.CheckInStatus.PENDING
        )
        if raw_status != RetreatAttendee.CheckInStatus.PENDING:
            assert_can_change_check_in_status(request.user, group)
        payload = _sanitize_attendee_payload(request.user, group, request.data)
        role = (payload.get("member_role") or "").strip()
        if payload.get("user") or role in (
            RetreatAttendee.MemberRole.LEADER,
            RetreatAttendee.MemberRole.VICE_LEADER,
            RetreatAttendee.MemberRole.TEACHER,
        ):
            assert_can_edit_attendee_details(request.user, group)
        data = dict(payload)
        data["group"] = group.id
        ser = RetreatAttendeeSerializer(
            data=data,
            context={"user": request.user, "group": group},
        )
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        linked_user = ser.validated_data.get("user")
        _assert_user_home_group_allows(user=linked_user, group=group)
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
        if attendee.check_in_status != RetreatAttendee.CheckInStatus.PENDING:
            attendee.check_in_status_manually_set = True
            stamp_fields.append("check_in_status_manually_set")
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
        assert_attendee_visible_to(request.user, attendee)
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
        # user 키는 연동 권한이 없으면 sanitize에서 제거하고, 권한 없으면 403 내지 않음
        # (조장 조원 수정 UI가 user를 실수로내도 프로필 수정은 가능해야 함)
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
        previous_user_id = attendee.user_id
        previous_member_role = attendee.member_role
        ser = RetreatAttendeeSerializer(
            attendee,
            data=payload,
            partial=True,
            context={"user": request.user, "group": group},
        )
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        if "member_role" in ser.validated_data:
            _assert_home_role_upgrade_allowed(
                attendee, str(ser.validated_data["member_role"])
            )
        linked_user = ser.validated_data.get("user", attendee.user)
        if "user" in ser.validated_data and linked_user is not None:
            _assert_user_home_group_allows(
                user=linked_user,
                group=group,
                exclude_attendee_id=attendee.id,
            )
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
        if "check_in_status" in ser.validated_data:
            attendee.check_in_status_manually_set = True
        if (
            "user" in payload
            and attendee.user_id is None
            and previous_user_id
            and previous_member_role
            in (
                RetreatAttendee.MemberRole.LEADER,
                RetreatAttendee.MemberRole.VICE_LEADER,
                RetreatAttendee.MemberRole.TEACHER,
            )
            and attendee.member_role
            in (
                RetreatAttendee.MemberRole.LEADER,
                RetreatAttendee.MemberRole.VICE_LEADER,
                RetreatAttendee.MemberRole.TEACHER,
            )
        ):
            attendee.member_role = RetreatAttendee.MemberRole.MEMBER
            attendee.save(update_fields=["member_role", "updated_at"])
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
                "check_in_status_manually_set",
                "checked_in_at",
                "checked_out_at",
                "lodging_stay_status",
                "updated_at",
            ]
        )
        if "member_role" in payload or "user" in payload:
            sync_membership_from_attendee(
                attendee,
                changed_by=request.user,
                previous_user_id=previous_user_id,
                previous_member_role=previous_member_role,
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
        assert_can_delete_attendee(request.user, attendee.group, attendee=attendee)
        before = serialize_model_fields(attendee, _ATTENDEE_FIELDS)
        event = attendee.group.event
        aid = attendee.id
        linked_user = attendee.user
        deleted_pickups = delete_pickups_for_attendee(attendee, changed_by=request.user)
        remove_membership_for_attendee(attendee, changed_by=request.user)
        attendee.delete()
        if linked_user is not None:
            from retreat.services.staff_application import (
                delete_staff_application_if_unassigned,
            )

            delete_staff_application_if_unassigned(
                linked_user, event, actor=request.user
            )
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
