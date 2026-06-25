"""조원 명단과 픽업(입회/출회) 요청 연동."""

from __future__ import annotations

from django.db.models import QuerySet
from django.utils import timezone

from retreat.models import RetreatAttendee, RetreatChangeLog, RetreatPickup
from retreat.services.audit import log_retreat_change


def pickups_for_attendee(attendee: RetreatAttendee) -> QuerySet[RetreatPickup]:
    """조원과 동일 조·이름으로 등록된 픽업 요청."""
    name = (attendee.name or "").strip()
    if not name or not attendee.group_id:
        return RetreatPickup.objects.none()
    return RetreatPickup.objects.filter(
        event_id=attendee.group.event_id,
        group_id=attendee.group_id,
        name=name,
    ).order_by("direction", "number", "id")


def serialize_pickup_for_attendee_preview(pickup: RetreatPickup) -> dict:
    train_time = ""
    if pickup.train_time:
        train_time = timezone.localtime(pickup.train_time).strftime("%Y-%m-%d %H:%M")
    return {
        "id": pickup.id,
        "direction": pickup.direction,
        "direction_display": pickup.get_direction_display(),
        "number": pickup.number,
        "train_time": train_time,
        "boarding_place": pickup.boarding_place,
    }


def delete_pickups_for_attendee(attendee: RetreatAttendee, *, changed_by) -> int:
    """조원 삭제 시 연결된 픽업 요청을 함께 제거한다."""
    event = attendee.group.event
    removed = 0
    for pickup in list(pickups_for_attendee(attendee)):
        before = {
            "direction": pickup.direction,
            "number": pickup.number,
            "group": pickup.group_id,
            "name": pickup.name,
            "train_time": pickup.train_time.isoformat() if pickup.train_time else None,
            "boarding_place": pickup.boarding_place,
            "contact": pickup.contact,
            "source": "attendee_delete",
        }
        pid = pickup.id
        pickup.delete()
        removed += 1
        log_retreat_change(
            user=changed_by,
            event=event,
            action=RetreatChangeLog.Action.DELETE,
            target_type=RetreatChangeLog.TargetType.PICKUP,
            target_id=pid,
            payload_before=before,
        )
    return removed
