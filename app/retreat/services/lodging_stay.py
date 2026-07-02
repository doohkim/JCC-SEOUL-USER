"""조원 숙박 상태 — denormalized lodging_stay_status 계산·동기화."""

from __future__ import annotations

from django.db.models import Q, QuerySet

from retreat.models import RetreatAttendee


def resolve_lodging_stay_status(attendee: RetreatAttendee) -> str:
    """참석·입퇴실·방 배정으로 숙박 상태 코드를 계산한다."""
    S = RetreatAttendee.LodgingStayStatus
    if (
        attendee.participation_status
        == RetreatAttendee.ParticipationStatus.ABSENT
    ):
        return S.ABSENT
    if attendee.check_in_status == RetreatAttendee.CheckInStatus.CHECKED_OUT:
        return S.ENDED
    if attendee.expected_check_in_at is None:
        return S.NO_STAY
    if attendee.lodging_room_id:
        return S.ACTIVE
    return S.UNASSIGNED


def sync_lodging_stay_status(attendee: RetreatAttendee) -> bool:
    """lodging_stay_status를 재계산해 변경 시 True."""
    new_status = resolve_lodging_stay_status(attendee)
    if attendee.lodging_stay_status == new_status:
        return False
    attendee.lodging_stay_status = new_status
    return True


LODGING_STAY_STATUS_LABELS: dict[str, str] = {
    RetreatAttendee.LodgingStayStatus.UNASSIGNED: "미배정",
    RetreatAttendee.LodgingStayStatus.ENDED: "숙박 종료",
    RetreatAttendee.LodgingStayStatus.NO_STAY: "입실 예정 없음",
    RetreatAttendee.LodgingStayStatus.ABSENT: "불참",
}

LODGING_STAY_FILTER_LABELS: dict[str, str] = {
    RetreatAttendee.LodgingStayStatus.ACTIVE: "배정됨",
    RetreatAttendee.LodgingStayStatus.UNASSIGNED: "미배정",
    RetreatAttendee.LodgingStayStatus.ENDED: "숙박 종료",
    RetreatAttendee.LodgingStayStatus.NO_STAY: "입실 예정 없음",
    RetreatAttendee.LodgingStayStatus.ABSENT: "불참",
}


def lodging_stay_filter_label(status: str) -> str:
    """필터 칩·UI용 한글 라벨."""
    return LODGING_STAY_FILTER_LABELS.get(status, status)


def lodging_stay_display(attendee: RetreatAttendee) -> str:
    """목록·API용 숙소 칸 표시 문자열."""
    S = RetreatAttendee.LodgingStayStatus
    status = attendee.lodging_stay_status or resolve_lodging_stay_status(attendee)
    if status == S.ACTIVE:
        room = attendee.lodging_room
        if room is not None:
            return f"{room.lodging.name} {room.number}"
        return "미배정"
    return LODGING_STAY_STATUS_LABELS.get(status, "-")


def is_lodging_stay_eligible(attendee: RetreatAttendee) -> bool:
    """숙박 대상 — active 또는 unassigned."""
    S = RetreatAttendee.LodgingStayStatus
    status = attendee.lodging_stay_status or resolve_lodging_stay_status(attendee)
    return status in (S.ACTIVE, S.UNASSIGNED)


def is_active_lodging_occupant(attendee: RetreatAttendee) -> bool:
    """활성 숙박자 — 정원·배정 인원 집계 기준."""
    S = RetreatAttendee.LodgingStayStatus
    status = attendee.lodging_stay_status or resolve_lodging_stay_status(attendee)
    return status == S.ACTIVE


def active_lodging_occupant_q(*, prefix: str = "") -> Q:
    """QuerySet filter: lodging_stay_status=active."""
    field = f"{prefix}lodging_stay_status"
    return Q(**{field: RetreatAttendee.LodgingStayStatus.ACTIVE})


def active_lodging_occupant_filter(qs: QuerySet) -> QuerySet:
    return qs.filter(lodging_stay_status=RetreatAttendee.LodgingStayStatus.ACTIVE)


def lodging_stay_eligible_filter(qs: QuerySet) -> QuerySet:
    """숙박 대상만."""
    S = RetreatAttendee.LodgingStayStatus
    P = RetreatAttendee.ParticipationStatus
    C = RetreatAttendee.CheckInStatus
    synced = Q(lodging_stay_status__in=(S.ACTIVE, S.UNASSIGNED))
    computed = Q(
        lodging_stay_status__isnull=True,
        participation_status=P.PARTICIPATING,
    ) & ~Q(check_in_status=C.CHECKED_OUT) & (
        Q(lodging_room__isnull=False)
        | Q(expected_check_in_at__isnull=False, lodging_room__isnull=True)
    )
    return qs.filter(synced | computed)


def count_active_occupants_for_room(room, *, exclude_pk: int | None = None) -> int:
    """호실 활성 숙박자 수 (정원 검사·드롭다운용)."""
    qs = room.attendees.filter(
        lodging_stay_status=RetreatAttendee.LodgingStayStatus.ACTIVE
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.count()


def persist_lodging_stay_status(attendee: RetreatAttendee) -> bool:
    """lodging_stay_status 재계산 후 DB 저장. 변경 시 True."""
    if not sync_lodging_stay_status(attendee):
        return False
    attendee.save(update_fields=["lodging_stay_status", "updated_at"])
    return True
