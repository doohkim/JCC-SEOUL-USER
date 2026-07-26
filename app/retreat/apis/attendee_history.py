"""조원별 변경 이력 조회 API.

기존 `RetreatChangeLog` 를 attendee 시점으로 재구성해서 노출한다.

- 입·퇴실 변경 이력: target_type=ATTENDEE 인 로그 중 check_in_status /
  checked_in_at / checked_out_at 변경이 일어난 항목.
- 세션별 출석 이력: target_type=ATTENDANCE 인 로그 중 payload 의
  attendee_id 가 해당 조원인 항목. 과거 페이로드에는 attendee_id 가 없을
  수 있으므로 enrollment id 기반 폴백 조회를 함께 사용한다.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from retreat.apis._common import get_group_or_403
from retreat.models import (
    RetreatAttendance,
    RetreatAttendee,
    RetreatChangeLog,
    RetreatSession,
    RetreatSessionAttendee,
)
from retreat.services.changelog_format import (
    CHECK_IN_LABELS,
    STATUS_LABELS,
    _actor_name,
    _is_auto_absent,
)
from retreat.services.effective_check_in import effective_status


_CHECK_IN_FIELDS = (
    "check_in_status",
    "checked_in_at",
    "checked_out_at",
    "expected_check_in_at",
    "expected_check_out_at",
)


def _format_dt(value):
    if not value:
        return None
    try:
        return value.isoformat() if hasattr(value, "isoformat") else str(value)
    except Exception:  # noqa: BLE001
        return str(value)


def _build_check_in_history(attendee: RetreatAttendee) -> list[dict]:
    logs = (
        RetreatChangeLog.objects.filter(
            target_type=RetreatChangeLog.TargetType.ATTENDEE,
            target_id=attendee.id,
        )
        .select_related("changed_by", "changed_by__profile")
        .order_by("-changed_at", "-id")
    )
    out: list[dict] = []
    for log in logs:
        before = log.payload_before or {}
        after = log.payload_after or {}
        relevant = {k for k in _CHECK_IN_FIELDS if before.get(k) != after.get(k)}
        is_create = log.action == RetreatChangeLog.Action.CREATE
        is_delete = log.action == RetreatChangeLog.Action.DELETE
        if not is_create and not is_delete and not relevant:
            continue
        prev_status = before.get("check_in_status")
        next_status = after.get("check_in_status")
        if is_create:
            summary = (
                f"조원 추가 ({CHECK_IN_LABELS.get(next_status, next_status or '-')})"
            )
        elif is_delete:
            summary = "조원 삭제"
        elif "check_in_status" in relevant:
            summary = (
                f"{CHECK_IN_LABELS.get(prev_status, prev_status or '-')} → "
                f"{CHECK_IN_LABELS.get(next_status, next_status or '-')}"
            )
        else:
            stamps = []
            if "expected_check_in_at" in relevant:
                stamps.append("예상 입실 시각 수정")
            if "expected_check_out_at" in relevant:
                stamps.append("예상 퇴실 시각 수정")
            if "checked_in_at" in relevant:
                stamps.append("실제 입실 시각 수정")
            if "checked_out_at" in relevant:
                stamps.append("실제 퇴실 시각 수정")
            summary = " · ".join(stamps) or "이력 갱신"
        out.append(
            {
                "id": log.id,
                "action": log.action,
                "changed_at": _format_dt(log.changed_at),
                "actor": _actor_name(log),
                "summary": summary,
                "prev_status": prev_status,
                "next_status": next_status,
                "prev_status_label": CHECK_IN_LABELS.get(
                    prev_status, prev_status or ""
                ),
                "next_status_label": CHECK_IN_LABELS.get(
                    next_status, next_status or ""
                ),
                "checked_in_at_before": before.get("checked_in_at"),
                "checked_in_at_after": after.get("checked_in_at"),
                "checked_out_at_before": before.get("checked_out_at"),
                "checked_out_at_after": after.get("checked_out_at"),
                "expected_check_in_at_before": before.get("expected_check_in_at"),
                "expected_check_in_at_after": after.get("expected_check_in_at"),
                "expected_check_out_at_before": before.get("expected_check_out_at"),
                "expected_check_out_at_after": after.get("expected_check_out_at"),
            }
        )
    return out


def _build_attendance_history(attendee: RetreatAttendee) -> list[dict]:
    """세션별 출석 이력. 같은 세션 내 변경은 시간 역순으로 묶는다."""

    enrollment_ids = list(
        RetreatSessionAttendee.objects.filter(source_attendee=attendee).values_list(
            "id", flat=True
        )
    )

    attendance_ids = list(
        RetreatAttendance.objects.filter(enrollment_id__in=enrollment_ids).values_list(
            "id", flat=True
        )
    )

    logs_qs = (
        RetreatChangeLog.objects.filter(
            target_type=RetreatChangeLog.TargetType.ATTENDANCE,
            target_id__in=attendance_ids,
        )
        .select_related("changed_by", "changed_by__profile")
        .order_by("-changed_at", "-id")
        if attendance_ids
        else RetreatChangeLog.objects.none()
    )

    enrollments_by_id = {
        e.id: e
        for e in RetreatSessionAttendee.objects.filter(
            id__in=enrollment_ids
        ).select_related("session")
    }

    attendances_by_id = {
        a.id: a
        for a in RetreatAttendance.objects.filter(id__in=attendance_ids).select_related(
            "enrollment", "enrollment__session"
        )
    }

    session_buckets: dict[int, dict] = {}
    for log in logs_qs:
        after = log.payload_after or {}
        before = log.payload_before or {}
        session_id = after.get("session_id") or before.get("session_id")
        if not session_id:
            attendance = attendances_by_id.get(log.target_id)
            enrollment = getattr(attendance, "enrollment", None)
            session_id = getattr(enrollment, "session_id", None)
        if not session_id:
            continue
        bucket = session_buckets.setdefault(
            session_id,
            {
                "session_id": session_id,
                "entries": [],
            },
        )
        prev_status = before.get("status")
        next_status = after.get("status")
        is_auto = _is_auto_absent(after)
        if log.action == RetreatChangeLog.Action.CREATE:
            suffix = " · 자동 결석" if is_auto else ""
            summary = (
                f"{STATUS_LABELS.get(next_status, next_status or '-')} 기록{suffix}"
            )
        else:
            summary = (
                f"{STATUS_LABELS.get(prev_status, prev_status or '-')} → "
                f"{STATUS_LABELS.get(next_status, next_status or '-')}"
            )
        bucket["entries"].append(
            {
                "id": log.id,
                "action": log.action,
                "changed_at": _format_dt(log.changed_at),
                "actor": _actor_name(log),
                "summary": summary,
                "prev_status": prev_status,
                "next_status": next_status,
                "prev_status_label": STATUS_LABELS.get(prev_status, ""),
                "next_status_label": STATUS_LABELS.get(next_status, ""),
                "auto_default": is_auto,
                "note_before": before.get("note", ""),
                "note_after": after.get("note", ""),
            }
        )

    current_by_session: dict[int, RetreatAttendance] = {}
    for attendance in attendances_by_id.values():
        current_by_session[attendance.enrollment.session_id] = attendance

    sessions_qs = RetreatSession.objects.filter(
        id__in=set(list(session_buckets.keys()) + list(current_by_session.keys()))
    ).order_by("-occurs_at", "-id")

    sessions_out: list[dict] = []
    for session in sessions_qs:
        enrollment = next(
            (e for e in enrollments_by_id.values() if e.session_id == session.id),
            None,
        )
        current = current_by_session.get(session.id)
        bucket = session_buckets.get(session.id, {"entries": []})
        sessions_out.append(
            {
                "session_id": session.id,
                "session_name": session.name,
                "session_status": session.status,
                "session_status_label": session.get_status_display(),
                "occurs_at": _format_dt(session.occurs_at),
                "current_status": current.status if current else None,
                "current_status_label": (
                    STATUS_LABELS.get(current.status, "") if current else ""
                ),
                "current_note": current.note if current else "",
                "enrollment_id": enrollment.id if enrollment else None,
                "entries": bucket["entries"],
            }
        )
    return sessions_out


class RetreatAttendeeHistoryView(APIView):
    """조원 한 명의 입·퇴실 + 세션별 출석 history."""

    permission_classes = [IsAuthenticated]

    def get(self, request, attendee_id: int):
        attendee = get_object_or_404(
            RetreatAttendee.objects.select_related("group", "group__event"),
            pk=attendee_id,
        )
        get_group_or_403(request.user, attendee.group_id)
        return Response(
            {
                "attendee": {
                    "id": attendee.id,
                    "name": attendee.name,
                    "check_in_status": effective_status(attendee),
                    "check_in_status_label": CHECK_IN_LABELS.get(
                        effective_status(attendee), effective_status(attendee)
                    ),
                    "expected_check_in_at": _format_dt(attendee.expected_check_in_at),
                    "expected_check_out_at": _format_dt(attendee.expected_check_out_at),
                    "checked_in_at": _format_dt(attendee.checked_in_at),
                    "checked_out_at": _format_dt(attendee.checked_out_at),
                    "group_id": attendee.group_id,
                    "group_name": attendee.group.name,
                },
                "check_in_history": _build_check_in_history(attendee),
                "attendance_history": _build_attendance_history(attendee),
            }
        )
