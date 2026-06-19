"""수련회 타임테이블(일정표) 관리 API."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.models import RetreatChangeLog, RetreatEvent, RetreatTimetableEntry
from retreat.serializers import RetreatTimetableEntrySerializer
from retreat.services.audit import log_retreat_change
from users.permissions import (
    can_access_retreat_tab,
    is_retreat_council,
    is_retreat_staff,
)

def _log_payload(entry: RetreatTimetableEntry) -> dict:
    return {
        "id": entry.id,
        "day": str(entry.day),
        "start_time": entry.start_time.strftime("%H:%M") if entry.start_time else None,
        "end_day": str(entry.end_day) if entry.end_day else None,
        "end_time": entry.end_time.strftime("%H:%M") if entry.end_time else None,
        "title": entry.title,
        "location": entry.location,
    }


def _assert_event_access(user) -> None:
    if not can_access_retreat_tab(user):
        raise PermissionDenied


def _assert_can_view(user, event: RetreatEvent) -> None:
    _assert_event_access(user)
    if not (
        user.is_superuser
        or is_retreat_council(user, event)
        or is_retreat_staff(user, event)
    ):
        raise PermissionDenied("타임테이블 조회 권한이 없습니다.")


def _assert_can_manage(user, event: RetreatEvent) -> None:
    _assert_event_access(user)
    if not is_retreat_council(user, event):
        raise PermissionDenied("타임테이블 편집은 회장단(또는 슈퍼유저)만 가능합니다.")


class RetreatEventTimetableListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        _assert_can_view(request.user, event)
        qs = event.timetable_entries.all().order_by(
            "day", "start_time", "sort_order", "id"
        )
        return Response(RetreatTimetableEntrySerializer(qs, many=True).data)

    def post(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        _assert_can_manage(request.user, event)
        ser = RetreatTimetableEntrySerializer(
            data=request.data, context={"event": event}
        )
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        entry = ser.save(event=event, created_by=request.user)
        log_retreat_change(
            user=request.user,
            event=event,
            action=RetreatChangeLog.Action.CREATE,
            target_type=RetreatChangeLog.TargetType.TIMETABLE,
            target_id=entry.id,
            payload_after=_log_payload(entry),
        )
        return Response(
            RetreatTimetableEntrySerializer(entry).data,
            status=status.HTTP_201_CREATED,
        )


class RetreatTimetableEntryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, event_id: int, entry_id: int) -> RetreatTimetableEntry:
        return get_object_or_404(
            RetreatTimetableEntry.objects.select_related("event"),
            pk=entry_id,
            event_id=event_id,
        )

    def patch(self, request, event_id: int, entry_id: int):
        entry = self._get(event_id, entry_id)
        _assert_can_manage(request.user, entry.event)
        before = _log_payload(entry)
        ser = RetreatTimetableEntrySerializer(
            entry,
            data=request.data,
            partial=True,
            context={"event": entry.event},
        )
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        entry = ser.save()
        log_retreat_change(
            user=request.user,
            event=entry.event,
            action=RetreatChangeLog.Action.UPDATE,
            target_type=RetreatChangeLog.TargetType.TIMETABLE,
            target_id=entry.id,
            payload_before=before,
            payload_after=_log_payload(entry),
        )
        return Response(RetreatTimetableEntrySerializer(entry).data)

    def delete(self, request, event_id: int, entry_id: int):
        entry = self._get(event_id, entry_id)
        _assert_can_manage(request.user, entry.event)
        before = _log_payload(entry)
        event = entry.event
        eid = entry.id
        entry.delete()
        log_retreat_change(
            user=request.user,
            event=event,
            action=RetreatChangeLog.Action.DELETE,
            target_type=RetreatChangeLog.TargetType.TIMETABLE,
            target_id=eid,
            payload_before=before,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
