"""수련회 출석부 스냅샷 생성·마감 처리."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db import transaction

from retreat.models import (
    RetreatAttendance,
    RetreatAttendee,
    RetreatChangeLog,
    RetreatSession,
    RetreatSessionAttendee,
)
from retreat.services.audit import log_retreat_change


def _enrollment_payload(enrollment: RetreatSessionAttendee) -> dict:
    return {
        "id": enrollment.id,
        "session_id": enrollment.session_id,
        "source_attendee_id": enrollment.source_attendee_id,
        "source_group_id": enrollment.source_group_id,
        "name": enrollment.name,
        "phone": enrollment.phone,
        "gender": enrollment.gender,
        "memo": enrollment.memo,
        "check_in_status": enrollment.check_in_status,
        "group_name": enrollment.group_name,
        "region_id": enrollment.region_id_snapshot,
        "region_name": enrollment.region_name,
        "division_id": enrollment.division_id_snapshot,
        "division_name": enrollment.division_name,
        "sort_order": enrollment.sort_order,
    }


def _attendance_payload(attendance: RetreatAttendance) -> dict:
    return {
        "id": attendance.id,
        "enrollment_id": attendance.enrollment_id,
        "attendee_id": attendance.enrollment.source_attendee_id,
        "session_id": attendance.enrollment.session_id,
        "status": attendance.status,
        "note": attendance.note,
    }


def assert_session_mutable(session: RetreatSession) -> None:
    if session.status == RetreatSession.Status.CLOSED:
        raise PermissionDenied("마감된 출석부입니다.")


def _create_absent_attendance(
    enrollment: RetreatSessionAttendee,
    *,
    actor,
    reason: str,
) -> RetreatAttendance:
    attendance, created = RetreatAttendance.objects.get_or_create(
        enrollment=enrollment,
        defaults={
            "status": RetreatAttendance.Status.ABSENT,
            "checked_by": actor if getattr(actor, "is_authenticated", False) else None,
        },
    )
    if created:
        log_retreat_change(
            user=actor,
            event=enrollment.session.event,
            action=RetreatChangeLog.Action.CREATE,
            target_type=RetreatChangeLog.TargetType.ATTENDANCE,
            target_id=attendance.id,
            payload_before=None,
            payload_after={
                **_attendance_payload(attendance),
                reason: True,
            },
        )
    return attendance


@transaction.atomic
def snapshot_session_enrollments(
    session: RetreatSession,
    *,
    actor,
) -> list[RetreatSessionAttendee]:
    """출석부 생성 시점의 집회 전체 조원 명단을 복사한다."""

    attendees = (
        RetreatAttendee.objects.filter(group__event=session.event)
        .select_related("group", "group__region", "group__division")
        .order_by(
            "group__region__sort_order",
            "group__division__sort_order",
            "group__order",
            "sort_order",
            "name",
            "id",
        )
    )
    created_enrollments: list[RetreatSessionAttendee] = []
    for attendee in attendees:
        enrollment, created = RetreatSessionAttendee.objects.get_or_create(
            session=session,
            source_attendee=attendee,
            defaults=_enrollment_defaults(attendee),
        )
        if not created:
            continue
        created_enrollments.append(enrollment)
        log_retreat_change(
            user=actor,
            event=session.event,
            action=RetreatChangeLog.Action.CREATE,
            target_type=RetreatChangeLog.TargetType.ENROLLMENT,
            target_id=enrollment.id,
            payload_before=None,
            payload_after={
                **_enrollment_payload(enrollment),
                "snapshot_on_session_create": True,
            },
        )
        if enrollment.check_in_status in (
            RetreatAttendee.CheckInStatus.CHECKED_OUT,
            RetreatAttendee.CheckInStatus.PENDING,
        ):
            reason = (
                "auto_default_for_pending"
                if enrollment.check_in_status == RetreatAttendee.CheckInStatus.PENDING
                else "auto_default_for_checked_out"
            )
            _create_absent_attendance(
                enrollment,
                actor=actor,
                reason=reason,
            )
    return created_enrollments


def _enrollment_defaults(attendee: RetreatAttendee) -> dict:
    group = attendee.group
    return {
        "source_group": group,
        "name": attendee.name,
        "phone": attendee.phone,
        "gender": attendee.gender,
        "memo": attendee.memo,
        "check_in_status": attendee.check_in_status,
        "member_role": attendee.member_role,
        "group_name": group.name,
        "region_id_snapshot": group.region_id,
        "region_name": getattr(group.region, "name", "") or "",
        "division_id_snapshot": group.division_id,
        "division_name": getattr(group.division, "name", "") or "",
        "sort_order": attendee.sort_order,
    }


@transaction.atomic
def enroll_attendee_into_active_sessions(
    attendee: RetreatAttendee,
    *,
    actor,
) -> list[RetreatSessionAttendee]:
    """신규 조원을 현재 진행중인 출석부에만 결석 기본값으로 합류시킨다."""

    sessions = RetreatSession.objects.filter(
        event=attendee.group.event,
        status=RetreatSession.Status.ACTIVE,
    ).order_by("created_at", "id")

    created_enrollments: list[RetreatSessionAttendee] = []
    for session in sessions:
        enrollment, created = RetreatSessionAttendee.objects.get_or_create(
            session=session,
            source_attendee=attendee,
            defaults=_enrollment_defaults(attendee),
        )
        if not created:
            continue
        created_enrollments.append(enrollment)
        log_retreat_change(
            user=actor,
            event=session.event,
            action=RetreatChangeLog.Action.CREATE,
            target_type=RetreatChangeLog.TargetType.ENROLLMENT,
            target_id=enrollment.id,
            payload_before=None,
            payload_after={
                **_enrollment_payload(enrollment),
                "auto_join_active_session": True,
            },
        )
        _create_absent_attendance(
            enrollment,
            actor=actor,
            reason="auto_default_for_late_added_attendee",
        )
    return created_enrollments


@transaction.atomic
def close_session(session: RetreatSession, *, actor) -> RetreatSession:
    if session.status == RetreatSession.Status.CLOSED:
        return session
    before = {
        "status": session.status,
        "closed_at": session.closed_at.isoformat() if session.closed_at else None,
        "closed_by_id": session.closed_by_id,
    }
    session.mark_closed(actor)
    log_retreat_change(
        user=actor,
        event=session.event,
        action=RetreatChangeLog.Action.UPDATE,
        target_type=RetreatChangeLog.TargetType.SESSION,
        target_id=session.id,
        payload_before=before,
        payload_after={
            "status": session.status,
            "closed_at": session.closed_at.isoformat() if session.closed_at else None,
            "closed_by_id": session.closed_by_id,
        },
    )
    return session


@transaction.atomic
def reopen_session(session: RetreatSession, *, actor) -> RetreatSession:
    if session.status == RetreatSession.Status.ACTIVE:
        return session
    before = {
        "status": session.status,
        "closed_at": session.closed_at.isoformat() if session.closed_at else None,
        "closed_by_id": session.closed_by_id,
    }
    session.mark_reopened()
    log_retreat_change(
        user=actor,
        event=session.event,
        action=RetreatChangeLog.Action.UPDATE,
        target_type=RetreatChangeLog.TargetType.SESSION,
        target_id=session.id,
        payload_before=before,
        payload_after={
            "status": session.status,
            "closed_at": None,
            "closed_by_id": None,
        },
    )
    return session
