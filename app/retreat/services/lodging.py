"""숙소 호실 배정 검증 및 필터링.

`LodgingRoom.region` 과 `LodgingRoom.division` 은 호실 단위 진실의 원천이며,
둘 중 하나라도 비어있으면 미배정 호실로 간주되어 어떤 조에도 노출되지 않는다.
"""

from __future__ import annotations

from django.db.models import Q, QuerySet
from rest_framework.exceptions import ValidationError

from retreat.models import LodgingRoom, RetreatAttendee, RetreatEvent, RetreatGroup


def assert_room_can_accept(room: LodgingRoom, attendee: RetreatAttendee) -> None:
    """호실이 해당 조원을 받을 수 있는지 검증한다.

    - 행사 일치 (room.lodging.event_id == attendee.group.event_id)
    - 지역·부서 일치 — room.region 과 attendee.group.region 이 같고,
      room.division 과 attendee.group.division 도 같아야 함.
      둘 중 하나라도 비어있는 호실은 어떤 조에도 배정 불가.
    - capacity 가 0 이면 무제한, 그렇지 않으면 현재 인원 + 1 <= capacity
    - recommended_gender 가 male/female 이면 attendee.gender 가 일치해야 함
      (mixed/미지정은 통과)
    """

    if room.lodging.event_id != attendee.group.event_id:
        raise ValidationError(
            {"lodging_room": "이 호실은 조원이 속한 행사의 숙소가 아닙니다."}
        )

    if room.region_id is None or room.division_id is None:
        raise ValidationError(
            {
                "lodging_room": (
                    "이 호실은 지역·부서가 지정되지 않아 배정할 수 없습니다."
                )
            }
        )

    room_pair = (room.region_id, room.division_id)
    if room_pair not in attendee.group.scope_pairs():
        raise ValidationError(
            {
                "lodging_room": (
                    "이 호실은 조원이 속한 조의 지역·부서 범위에 포함되지 않습니다."
                )
            }
        )

    capacity = int(room.capacity or 0)
    if capacity > 0:
        current = room.attendees.exclude(pk=attendee.pk).count()
        if current + 1 > capacity:
            raise ValidationError(
                {
                    "lodging_room": (
                        f"호실 정원 {capacity}명을 초과합니다 (현재 {current}명)."
                    )
                }
            )

    rg = room.recommended_gender or ""
    if rg in (LodgingRoom.Gender.MALE, LodgingRoom.Gender.FEMALE):
        if attendee.gender != rg:
            raise ValidationError(
                {
                    "lodging_room": (
                        "이 호실의 권장 성별과 조원 성별이 일치하지 않습니다."
                    )
                }
            )


def _base_rooms_qs(event: RetreatEvent) -> QuerySet[LodgingRoom]:
    return LodgingRoom.objects.filter(lodging__event=event).select_related(
        "lodging",
        "lodging__region",
        "region",
        "division",
    )


def rooms_for_group(group: RetreatGroup) -> QuerySet[LodgingRoom]:
    """조의 대표·보조 (지역, 부서) 범위에 해당하는 호실 queryset."""

    pairs = group.scope_pairs()
    if not pairs:
        return LodgingRoom.objects.none()
    scope_q = Q()
    for region_id, division_id in pairs:
        scope_q |= Q(region_id=region_id, division_id=division_id)
    return _base_rooms_qs(group.event).filter(scope_q).order_by(
        "lodging__sort_order", "lodging__name", "sort_order", "number", "id"
    )


def rooms_for_event_region_division(
    event: RetreatEvent,
    region_id: int | None,
    division_id: int | None,
) -> QuerySet[LodgingRoom]:
    """행사 + 조의 region/division 에 매칭되는 호실 queryset.

    region 또는 division 이 비어 있으면 빈 queryset 을 돌려준다 (미배정 호실은
    어떤 조에도 노출되지 않으며, region/division 이 없는 조는 호실을 받을 수 없다).
    """

    if region_id is None or division_id is None:
        return LodgingRoom.objects.none()
    return _base_rooms_qs(event).filter(
        region_id=region_id, division_id=division_id
    ).order_by(
        "lodging__sort_order", "lodging__name", "sort_order", "number", "id"
    )


def rooms_for_event_and_region(
    event: RetreatEvent, region_id: int | None
) -> QuerySet[LodgingRoom]:
    """방배정 페이지에서 region 별 호실을 그룹화하기 위한 헬퍼.

    region 이 일치하는 호실(division 무관)을 모두 반환한다. 미배정 호실
    (region IS NULL) 은 region 컬럼이 None 인 호출에서만 보인다.
    """

    if region_id is None:
        return _base_rooms_qs(event).filter(region__isnull=True).order_by(
            "lodging__sort_order", "lodging__name", "sort_order", "number", "id"
        )
    return _base_rooms_qs(event).filter(region_id=region_id).order_by(
        "lodging__sort_order", "lodging__name", "sort_order", "number", "id"
    )
