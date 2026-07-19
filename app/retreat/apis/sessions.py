"""출석부(세션) CRUD API."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.models import RetreatChangeLog, RetreatEvent, RetreatSession
from retreat.serializers import RetreatSessionSerializer
from retreat.services.audit import log_retreat_change, serialize_model_fields
from retreat.services.enrollment import (
    assert_session_mutable,
    close_session,
    reopen_session,
)
from users.permissions import (
    can_access_retreat_tab,
    can_manage_retreat_sessions,
    visible_retreat_sessions_for,
)

_SESSION_FIELDS = [
    "id",
    "name",
    "occurs_at",
    "sequence",
    "location",
    "status",
    "closed_at",
    "closed_by_id",
    "event_id",
]


def _assert_event_access(user, event: RetreatEvent) -> None:
    if not can_access_retreat_tab(user):
        raise PermissionDenied("수련회 접근 권한이 없습니다.")


def _assert_can_manage_sessions(user, event: RetreatEvent) -> None:
    _assert_event_access(user, event)
    if not can_manage_retreat_sessions(user, event):
        raise PermissionDenied(
            "출석부 관리는 수련회 회장단(또는 슈퍼유저)만 가능합니다."
        )


class RetreatEventSessionListCreateView(APIView):
    """GET 목록 / POST 생성."""

    permission_classes = [IsAuthenticated]

    def get(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        _assert_event_access(request.user, event)
        sessions = (
            visible_retreat_sessions_for(request.user, event)
            .select_related("created_by", "closed_by")
            .order_by("-created_at", "-id")
        )
        return Response(RetreatSessionSerializer(sessions, many=True).data)

    def post(self, request, event_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        _assert_can_manage_sessions(request.user, event)
        ser = RetreatSessionSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        session = ser.save(created_by=request.user, event=event)
        # 처음부터 '마감' 상태로 만들면 closed_by/closed_at 보정 후 저장.
        if session.status == RetreatSession.Status.CLOSED:
            session.mark_closed(user=request.user)
        log_retreat_change(
            user=request.user,
            event=event,
            action=RetreatChangeLog.Action.CREATE,
            target_type=RetreatChangeLog.TargetType.SESSION,
            target_id=session.id,
            payload_after=serialize_model_fields(session, _SESSION_FIELDS),
        )
        return Response(
            RetreatSessionSerializer(session).data,
            status=status.HTTP_201_CREATED,
        )


class RetreatSessionDetailView(APIView):
    """PATCH / DELETE 단일 출석부."""

    permission_classes = [IsAuthenticated]

    def _get_session(self, request, event_id: int, session_id: int) -> RetreatSession:
        event = get_object_or_404(RetreatEvent, pk=event_id)
        return get_object_or_404(
            visible_retreat_sessions_for(request.user, event).select_related(
                "event", "created_by", "closed_by"
            ),
            pk=session_id,
        )

    def get(self, request, event_id: int, session_id: int):
        session = self._get_session(request, event_id, session_id)
        _assert_event_access(request.user, session.event)
        return Response(RetreatSessionSerializer(session).data)

    def patch(self, request, event_id: int, session_id: int):
        session = self._get_session(request, event_id, session_id)
        _assert_can_manage_sessions(request.user, session.event)
        assert_session_mutable(session)
        before = serialize_model_fields(session, _SESSION_FIELDS)
        ser = RetreatSessionSerializer(session, data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        session = ser.save()
        log_retreat_change(
            user=request.user,
            event=session.event,
            action=RetreatChangeLog.Action.UPDATE,
            target_type=RetreatChangeLog.TargetType.SESSION,
            target_id=session.id,
            payload_before=before,
            payload_after=serialize_model_fields(session, _SESSION_FIELDS),
        )
        return Response(RetreatSessionSerializer(session).data)

    def delete(self, request, event_id: int, session_id: int):
        session = self._get_session(request, event_id, session_id)
        _assert_can_manage_sessions(request.user, session.event)
        assert_session_mutable(session)
        before = serialize_model_fields(session, _SESSION_FIELDS)
        event = session.event
        sid = session.id
        session.delete()
        log_retreat_change(
            user=request.user,
            event=event,
            action=RetreatChangeLog.Action.DELETE,
            target_type=RetreatChangeLog.TargetType.SESSION,
            target_id=sid,
            payload_before=before,
            payload_after=None,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class RetreatSessionCloseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_id: int, session_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        _assert_can_manage_sessions(request.user, event)
        session = get_object_or_404(RetreatSession, pk=session_id, event=event)
        close_session(session, actor=request.user)
        return Response(RetreatSessionSerializer(session).data)


class RetreatSessionReopenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, event_id: int, session_id: int):
        event = get_object_or_404(RetreatEvent, pk=event_id)
        _assert_can_manage_sessions(request.user, event)
        session = get_object_or_404(RetreatSession, pk=session_id, event=event)
        reopen_session(session, actor=request.user)
        return Response(RetreatSessionSerializer(session).data)
