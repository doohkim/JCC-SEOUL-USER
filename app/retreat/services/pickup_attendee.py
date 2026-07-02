"""조원 명단과 픽업(입회/출회) 요청 연동."""

from __future__ import annotations

from django.db.models import QuerySet
from django.utils import timezone

from retreat.models import RetreatAttendee, RetreatChangeLog, RetreatGroup, RetreatPickup
from retreat.services.audit import log_retreat_change
from retreat.services.participation import participating_filter


def pickup_attendee_for_name(
    group: RetreatGroup | None, name: str
) -> RetreatAttendee | None:
    """조·이름으로 참석 조원 1건 (불참 제외)."""
    if group is None:
        return None
    trimmed = (name or "").strip()
    if not trimmed:
        return None
    return participating_filter(
        RetreatAttendee.objects.filter(group=group, name=trimmed)
    ).first()


def pickup_name_on_roster(group: RetreatGroup | None, name: str) -> bool:
    """조·이름이 참석 조원 명단에 있는지 (불참 제외)."""
    if group is None:
        return True
    return pickup_attendee_for_name(group, name) is not None


def pickup_name_eligibility_error(
    group: RetreatGroup | None, name: str, direction: str
) -> str | None:
    """입회·출회별 픽업 대상 입퇴실 상태 검증. 거부 시 한글 메시지."""
    att = pickup_attendee_for_name(group, name)
    if att is None:
        return None
    S = RetreatAttendee.CheckInStatus
    if direction == RetreatPickup.Direction.ARRIVAL:
        if att.check_in_status != S.PENDING:
            return "입회 차량 요청은 입실전 상태 조원만 등록할 수 있습니다."
    elif direction == RetreatPickup.Direction.DEPARTURE:
        if att.check_in_status != S.CHECKED_IN:
            return "출회 차량 요청은 입실 상태 조원만 등록할 수 있습니다."
    return None


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
