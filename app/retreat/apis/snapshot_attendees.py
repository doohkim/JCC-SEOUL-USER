"""마감 출석부 전용 스냅샷 조원 API."""

from __future__ import annotations

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.apis._common import get_group_or_403
from retreat.models import (
    RetreatAttendance,
    RetreatAttendee,
    RetreatChangeLog,
    RetreatGroup,
    RetreatSession,
    RetreatSessionAttendee,
)
from retreat.serializers import RetreatSessionAttendeeAdminSerializer
from retreat.services.audit import log_retreat_change
from retreat.services.enrollment import _attendance_payload, _enrollment_payload
from users.permissions import can_manage_retreat_sessions


def _assert_can_manage_snapshot(user, event) -> None:
    if not can_manage_retreat_sessions(user, event):
        raise PermissionDenied("마감 출석부 조원 관리는 회장단(또는 슈퍼유저)만 가능합니다.")


def _assert_snapshot_only(enrollment: RetreatSessionAttendee) -> None:
    if enrollment.source_attendee_id is not None:
        raise ValidationError(
            {"detail": "현재 명단에 연결된 조원은 이 API로 수정할 수 없습니다."}
        )


class RetreatSessionGroupSnapshotAttendeesView(APIView):
    """마감 출석부에만 조원 스냅샷 추가."""

    permission_classes = [IsAuthenticated]

    def post(self, request, session_id: int, group_id: int):
        session = get_object_or_404(
            RetreatSession.objects.select_related("event"),
            pk=session_id,
        )
        group = get_object_or_404(
            RetreatGroup.objects.select_related("region", "division", "event"),
            pk=group_id,
        )
        if session.event_id != group.event_id:
            raise ValidationError({"detail": "출석부와 조가 같은 집회에 속해야 합니다."})
        get_group_or_403(request.user, group_id)
        _assert_can_manage_snapshot(request.user, session.event)
        if session.status != RetreatSession.Status.CLOSED:
            raise ValidationError(
                {"detail": "마감된 출석부에만 스냅샷 조원을 추가할 수 있습니다."}
            )

        ser = RetreatSessionAttendeeAdminSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            enrollment = RetreatSessionAttendee.objects.create(
                session=session,
                source_attendee=None,
                source_group=group,
                name=ser.validated_data["name"],
                phone=ser.validated_data.get("phone", "") or "",
                gender=ser.validated_data.get("gender", "") or "",
                memo=ser.validated_data.get("memo", "") or "",
                check_in_status=ser.validated_data.get(
                    "check_in_status", RetreatAttendee.CheckInStatus.CHECKED_IN
                ),
                group_name=group.name,
                region_id_snapshot=group.region_id,
                region_name=getattr(group.region, "name", "") or "",
                division_id_snapshot=group.division_id,
                division_name=getattr(group.division, "name", "") or "",
                sort_order=ser.validated_data.get("sort_order", 0),
            )
            attendance = RetreatAttendance.objects.create(
                enrollment=enrollment,
                status=RetreatAttendance.Status.ABSENT,
                checked_by=request.user,
            )
            log_retreat_change(
                user=request.user,
                event=session.event,
                action=RetreatChangeLog.Action.CREATE,
                target_type=RetreatChangeLog.TargetType.ENROLLMENT,
                target_id=enrollment.id,
                payload_before=None,
                payload_after={
                    **_enrollment_payload(enrollment),
                    "admin_manual_add": True,
                },
            )
            log_retreat_change(
                user=request.user,
                event=session.event,
                action=RetreatChangeLog.Action.CREATE,
                target_type=RetreatChangeLog.TargetType.ATTENDANCE,
                target_id=attendance.id,
                payload_before=None,
                payload_after={
                    **_attendance_payload(attendance),
                    "auto_default_for_admin_manual_add": True,
                },
            )

        return Response(
            RetreatSessionAttendeeAdminSerializer(enrollment).data,
            status=status.HTTP_201_CREATED,
        )


class RetreatSnapshotAttendeeDetailView(APIView):
    """스냅샷 전용 조원 수정/삭제 (마감 상태에서도 허용)."""

    permission_classes = [IsAuthenticated]

    def _get_enrollment(self, request, enrollment_id: int) -> RetreatSessionAttendee:
        enrollment = get_object_or_404(
            RetreatSessionAttendee.objects.select_related(
                "session", "session__event", "source_group"
            ),
            pk=enrollment_id,
        )
        if enrollment.source_group_id:
            get_group_or_403(request.user, enrollment.source_group_id)
        _assert_can_manage_snapshot(request.user, enrollment.session.event)
        return enrollment

    def patch(self, request, enrollment_id: int):
        enrollment = self._get_enrollment(request, enrollment_id)
        _assert_snapshot_only(enrollment)

        before = _enrollment_payload(enrollment)
        ser = RetreatSessionAttendeeAdminSerializer(
            enrollment, data=request.data, partial=True
        )
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        enrollment = ser.save()
        log_retreat_change(
            user=request.user,
            event=enrollment.session.event,
            action=RetreatChangeLog.Action.UPDATE,
            target_type=RetreatChangeLog.TargetType.ENROLLMENT,
            target_id=enrollment.id,
            payload_before=before,
            payload_after={
                **_enrollment_payload(enrollment),
                "admin_manual_edit": True,
            },
        )
        return Response(RetreatSessionAttendeeAdminSerializer(enrollment).data)

    def delete(self, request, enrollment_id: int):
        enrollment = self._get_enrollment(request, enrollment_id)
        _assert_snapshot_only(enrollment)

        before = _enrollment_payload(enrollment)
        event = enrollment.session.event
        eid = enrollment.id
        enrollment.delete()
        log_retreat_change(
            user=request.user,
            event=event,
            action=RetreatChangeLog.Action.DELETE,
            target_type=RetreatChangeLog.TargetType.ENROLLMENT,
            target_id=eid,
            payload_before=before,
            payload_after=None,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
