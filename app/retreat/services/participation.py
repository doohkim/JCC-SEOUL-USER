"""집회 단위 참석/불참 — 집계·숙소·픽업 제외 규칙."""

from __future__ import annotations

from django.db.models import QuerySet

from retreat.models import RetreatAttendance, RetreatAttendee, RetreatSessionAttendee


def is_participating(attendee: RetreatAttendee) -> bool:
    return attendee.participation_status != RetreatAttendee.ParticipationStatus.ABSENT


def participating_filter(qs: QuerySet) -> QuerySet:
    return qs.exclude(participation_status=RetreatAttendee.ParticipationStatus.ABSENT)


def absent_attendee_keys(group_ids: list[int]) -> set[tuple[int, str]]:
    """(group_id, name) 집합 — 픽업·차량 집계 제외용."""
    if not group_ids:
        return set()
    return {
        (gid, name)
        for gid, name in RetreatAttendee.objects.filter(
            group_id__in=group_ids,
            participation_status=RetreatAttendee.ParticipationStatus.ABSENT,
        ).values_list("group_id", "name")
    }


def pickup_visible_for_participation(
    pickup,
    *,
    absent_keys: set[tuple[int, str]],
) -> bool:
    if not pickup.group_id:
        return True
    return (pickup.group_id, pickup.name) not in absent_keys


def apply_participation_change(
    attendee: RetreatAttendee,
    *,
    previous: str,
    new: str,
    actor,
) -> list[str]:
    """불참 전환 시 숙소 해제·세션 결석 동기화. 참석 복귀 시 데이터는 유지."""
    update_fields: list[str] = []
    if (
        previous != RetreatAttendee.ParticipationStatus.ABSENT
        and new == RetreatAttendee.ParticipationStatus.ABSENT
    ):
        if attendee.lodging_room_id:
            attendee.lodging_room_id = None
            update_fields.append("lodging_room_id")
        _sync_sessions_absent(attendee, actor=actor)
    return update_fields


def _sync_sessions_absent(attendee: RetreatAttendee, *, actor) -> None:
    from retreat.models import RetreatChangeLog
    from retreat.services.audit import log_retreat_change
    from retreat.services.enrollment import _attendance_payload

    enrollments = RetreatSessionAttendee.objects.filter(
        source_attendee=attendee
    ).select_related("session", "session__event")
    for enrollment in enrollments:
        prev = RetreatAttendance.objects.filter(enrollment=enrollment).first()
        before_payload = (
            {
                "status": prev.status,
                "note": prev.note,
                "enrollment_id": enrollment.id,
                "attendee_id": attendee.id,
                "session_id": enrollment.session_id,
            }
            if prev
            else None
        )
        attendance, created = RetreatAttendance.objects.update_or_create(
            enrollment=enrollment,
            defaults={
                "status": RetreatAttendance.Status.ABSENT,
                "checked_by": (
                    actor if getattr(actor, "is_authenticated", False) else None
                ),
            },
        )
        if created or (
            before_payload and before_payload.get("status") != attendance.status
        ):
            log_retreat_change(
                user=actor,
                event=enrollment.session.event,
                action=(
                    RetreatChangeLog.Action.CREATE
                    if created
                    else RetreatChangeLog.Action.UPDATE
                ),
                target_type=RetreatChangeLog.TargetType.ATTENDANCE,
                target_id=attendance.id,
                payload_before=before_payload,
                payload_after={
                    **_attendance_payload(attendance),
                    "master_participation_absent": True,
                },
            )
