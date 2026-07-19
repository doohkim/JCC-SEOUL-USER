"""출석 일괄 upsert API."""

from __future__ import annotations

import hmac

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.apis._common import assert_can_mutate_group
from retreat.models import (
    RetreatAttendance,
    RetreatAttendee,
    RetreatChangeLog,
    RetreatSession,
    RetreatSessionAttendee,
)
from retreat.services.enrollment import assert_session_mutable
from retreat.services.audit import log_retreat_change
from retreat.serializers import (
    RetreatAttendanceBulkUpsertSerializer,
    RetreatAttendanceSerializer,
)
from users.permissions import visible_retreat_groups_for, visible_retreat_sessions_for


def _retreat_api_token() -> str:
    """외부 공개 출석 API 토큰을 안전하게 조회한다."""
    direct = str(getattr(settings, "RETREAT", "") or "").strip()
    if direct:
        return direct
    secrets_obj = getattr(settings, "secrets", None)
    return str(getattr(secrets_obj, "RETREAT", "") or "").strip()


class RetreatAttendanceBulkUpsertView(APIView):
    """세션 단위 일괄 출석 upsert.

    POST JSON 예::

        {
          "session_id": 12,
          "rows": [
            {"enrollment_id": 1, "status": "present"},
            {"enrollment_id": 2, "status": "absent", "note": "감기"}
          ]
        }

    멱등성:
      - 동일 enrollment 행이 있으면 status/note/checked_by 만 갱신.
      - 권한 없는 enrollment 가 섞이면 전체 트랜잭션 롤백 + 403.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = RetreatAttendanceBulkUpsertSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        session_id = ser.validated_data["session_id"]
        rows = ser.validated_data["rows"]

        session = get_object_or_404(
            RetreatSession.objects.select_related("event"),
            pk=session_id,
        )
        event = session.event
        if not visible_retreat_sessions_for(request.user, event).filter(pk=session.id).exists():
            raise PermissionDenied("이 출석부를 볼 권한이 없습니다.")
        assert_session_mutable(session)

        # 가시 그룹 캐싱.
        visible_group_ids = set(
            visible_retreat_groups_for(request.user, event).values_list("id", flat=True)
        )

        enrollment_ids = [r["enrollment_id"] for r in rows if r.get("enrollment_id")]
        attendee_ids = [r["attendee_id"] for r in rows if r.get("attendee_id")]
        enrollment_map = {
            e.id: e
            for e in RetreatSessionAttendee.objects.filter(
                pk__in=enrollment_ids,
                session=session,
            ).select_related("session", "source_group", "source_attendee")
        }
        if attendee_ids:
            for e in RetreatSessionAttendee.objects.filter(
                session=session,
                source_attendee_id__in=attendee_ids,
            ).select_related("session", "source_group", "source_attendee"):
                enrollment_map[e.id] = e

        # 입력 검증: 모든 enrollment 가 해당 세션에 속하고, 본인 가시 그룹이어야 함.
        resolved_rows = []
        for r in rows:
            enrollment = None
            if r.get("enrollment_id"):
                enrollment = enrollment_map.get(r["enrollment_id"])
            elif r.get("attendee_id"):
                enrollment = next(
                    (
                        e
                        for e in enrollment_map.values()
                        if e.source_attendee_id == r["attendee_id"]
                    ),
                    None,
                )
            if enrollment is None:
                return Response(
                    {"detail": "출석부에 포함되지 않은 조원입니다."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if enrollment.source_group_id not in visible_group_ids:
                raise PermissionDenied(
                    f"enrollment_id={enrollment.id} 가 본인이 볼 수 없는 조에 속해 있습니다."
                )
            # 추가로 변경 권한도 확인 (staff/leader/superuser).
            assert_can_mutate_group(request.user, enrollment.source_group)
            source_attendee = enrollment.source_attendee
            if (
                source_attendee
                and source_attendee.participation_status
                == RetreatAttendee.ParticipationStatus.ABSENT
                and r["status"] == RetreatAttendance.Status.PRESENT
            ):
                return Response(
                    {
                        "detail": (
                            f"enrollment_id={enrollment.id} (집회 불참)는 "
                            "참석으로 기록할 수 없습니다."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if enrollment.check_in_status == RetreatAttendee.CheckInStatus.PENDING:
                return Response(
                    {
                        "detail": (
                            f"enrollment_id={enrollment.id} (입실전)는 출석을 설정할 수 없습니다."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if (
                enrollment.check_in_status == RetreatAttendee.CheckInStatus.CHECKED_OUT
                and r["status"] == RetreatAttendance.Status.PRESENT
            ):
                return Response(
                    {
                        "detail": (
                            f"enrollment_id={enrollment.id} (퇴실)는 참석으로 변경할 수 없습니다."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            resolved_rows.append((enrollment, r))

        existing = {
            a.enrollment_id: a
            for a in RetreatAttendance.objects.filter(
                enrollment_id__in=[e.id for e, _ in resolved_rows]
            )
        }

        created = 0
        updated = 0
        result_objs: list[RetreatAttendance] = []
        with transaction.atomic():
            for enrollment, r in resolved_rows:
                defaults = {
                    "status": r["status"],
                    "note": r.get("note", "") or "",
                    "checked_by": request.user,
                }
                prev = existing.get(enrollment.id)
                before_payload = None
                if prev:
                    before_payload = {
                        "status": prev.status,
                        "note": prev.note,
                        "enrollment_id": enrollment.id,
                        "attendee_id": enrollment.source_attendee_id,
                        "session_id": session.id,
                    }
                obj, was_created = RetreatAttendance.objects.update_or_create(
                    enrollment=enrollment, defaults=defaults
                )
                after_payload = {
                    "status": obj.status,
                    "note": obj.note,
                    "enrollment_id": enrollment.id,
                    "attendee_id": enrollment.source_attendee_id,
                    "session_id": session.id,
                }
                if was_created or (
                    before_payload
                    and before_payload.get("status") != obj.status
                ) or (
                    before_payload and before_payload.get("note") != obj.note
                ):
                    log_retreat_change(
                        user=request.user,
                        event=event,
                        action=RetreatChangeLog.Action.CREATE
                        if was_created
                        else RetreatChangeLog.Action.UPDATE,
                        target_type=RetreatChangeLog.TargetType.ATTENDANCE,
                        target_id=obj.id,
                        payload_before=before_payload,
                        payload_after=after_payload,
                    )
                if was_created:
                    created += 1
                else:
                    updated += 1
                result_objs.append(obj)

        return Response(
            {
                "session_id": session.id,
                "created": created,
                "updated": updated,
                "rows": RetreatAttendanceSerializer(result_objs, many=True).data,
            },
            status=status.HTTP_200_OK,
        )

class RetreatSessionAttendanceNamesView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, session_id: int):
        token = (request.headers.get("X-Retreat-Token") or "").strip()
        expected = _retreat_api_token()
        if not token or not expected or not hmac.compare_digest(token, expected):
            return Response({"detail": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        session = get_object_or_404(
            RetreatSession.objects.select_related("event"),
            pk=session_id,
        )
        rows = (
            RetreatAttendance.objects.filter(
                enrollment__session=session,
                status=RetreatAttendance.Status.PRESENT,
            )
            .select_related("enrollment")
            .values("enrollment__group_name", "enrollment__name")
        )
        return Response({
            "attendees": [
                {
                    "group_name": row["enrollment__group_name"],
                    "name": row["enrollment__name"],
                } for row in rows
            ]
        })