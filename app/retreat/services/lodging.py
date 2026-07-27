"""숙소 호실 배정 검증 및 필터링.

`LodgingRoom.region` 과 `LodgingRoom.division` 은 호실 단위 진실의 원천이며,
둘 중 하나라도 비어있으면 미배정 호실로 간주되어 어떤 조에도 노출되지 않는다.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from django.db.models import Count, Q, QuerySet
from rest_framework.exceptions import ValidationError

from retreat.models import LodgingRoom, RetreatAttendee, RetreatEvent, RetreatGroup
from retreat.services.lodging_stay import (
    active_lodging_occupant_q,
    count_active_occupants_for_room,
)
from retreat.services.participation import is_participating
from users.models import Division, Region


def assert_room_can_accept(room: LodgingRoom, attendee: RetreatAttendee) -> None:
    """호실이 해당 조원을 받을 수 있는지 검증한다.

    - 집회 일치 (room.lodging.event_id == attendee.group.event_id)
    - 지역·부서 일치 — room.region 과 attendee.group.region 이 같고,
      room.division 과 attendee.group.division 도 같아야 함.
      둘 중 하나라도 비어있는 호실은 어떤 조에도 배정 불가.
    - capacity 가 0 이면 무제한, 그렇지 않으면 현재 인원 + 1 <= capacity
    - recommended_gender 가 male/female 이면 attendee.gender 가 일치해야 함
      (mixed/미지정은 통과)
    """
    if not is_participating(attendee):
        raise ValidationError(
            {"lodging_room": "불참 조원에게는 숙소를 배정할 수 없습니다."}
        )

    if room.lodging.event_id != attendee.group.event_id:
        raise ValidationError(
            {"lodging_room": "이 호실은 조원이 속한 집회의 숙소가 아닙니다."}
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
        current = count_active_occupants_for_room(room, exclude_pk=attendee.pk)
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
    return (
        _base_rooms_qs(group.event)
        .filter(scope_q)
        .order_by("lodging__sort_order", "lodging__name", "sort_order", "number", "id")
    )


def rooms_for_group_with_counts(group: RetreatGroup) -> QuerySet[LodgingRoom]:
    """배정 드롭다운용 — 조 범위 호실 + 현재 활성 배정 인원 수."""
    return rooms_for_group(group).annotate(
        assigned_count=Count(
            "attendees",
            filter=active_lodging_occupant_q(prefix="attendees__"),
        ),
    )


def room_assignment_option(room: LodgingRoom) -> dict:
    """조원 수정 모달 숙소 옵션 JSON."""
    assigned = getattr(room, "assigned_count", None)
    if assigned is None:
        assigned = count_active_occupants_for_room(room)
    return {
        "id": room.id,
        "label": f"{room.lodging.name} {room.number}",
        "capacity": int(room.capacity or 0),
        "assigned_count": assigned,
        "recommended_gender": room.recommended_gender or "",
    }


def room_assignment_options_for_groups(
    event: RetreatEvent,
    groups: Iterable[RetreatGroup],
) -> dict[int, list[dict]]:
    """집회 호실을 한 번만 조회해 조별 배정 옵션으로 나눈다."""
    rooms = list(
        _base_rooms_qs(event)
        .filter(region_id__isnull=False, division_id__isnull=False)
        .annotate(
            assigned_count=Count(
                "attendees",
                filter=active_lodging_occupant_q(prefix="attendees__"),
            )
        )
        .order_by("lodging__sort_order", "lodging__name", "sort_order", "number", "id")
    )
    room_options = [(room, room_assignment_option(room)) for room in rooms]
    result: dict[int, list[dict]] = {}
    for group in groups:
        scope_pairs = group.scope_pairs()
        result[group.id] = [
            option
            for room, option in room_options
            if (room.region_id, room.division_id) in scope_pairs
        ]
    return result


def room_visible_in_assignment_picker(
    room: LodgingRoom,
    *,
    gender: str,
    current_room_id: int | None = None,
) -> bool:
    """배정 드롭다운 노출 여부 — 만실·성별 불일치 호실 제외 (현재 배정 호실은 유지)."""
    rg = room.recommended_gender or ""
    if rg in (LodgingRoom.Gender.MALE, LodgingRoom.Gender.FEMALE):
        if gender != rg:
            return False

    capacity = int(room.capacity or 0)
    if capacity == 0:
        return True
    if current_room_id is not None and room.id == current_room_id:
        return True

    assigned = getattr(room, "assigned_count", None)
    if assigned is None:
        assigned = count_active_occupants_for_room(room)
    return assigned < capacity


def rooms_for_event_region_division(
    event: RetreatEvent,
    region_id: int | None,
    division_id: int | None,
) -> QuerySet[LodgingRoom]:
    """집회 + 조의 region/division 에 매칭되는 호실 queryset.

    region 또는 division 이 비어 있으면 빈 queryset 을 돌려준다 (미배정 호실은
    어떤 조에도 노출되지 않으며, region/division 이 없는 조는 호실을 받을 수 없다).
    """

    if region_id is None or division_id is None:
        return LodgingRoom.objects.none()
    return (
        _base_rooms_qs(event)
        .filter(region_id=region_id, division_id=division_id)
        .order_by("lodging__sort_order", "lodging__name", "sort_order", "number", "id")
    )


def rooms_for_event_and_region(
    event: RetreatEvent, region_id: int | None
) -> QuerySet[LodgingRoom]:
    """집회·지역에 속한 호실 queryset (division 무관).

    region 이 None 이면 region 이 비어 있는 미배정 호실만 반환한다.
    """

    if region_id is None:
        return (
            _base_rooms_qs(event)
            .filter(region__isnull=True)
            .order_by(
                "lodging__sort_order", "lodging__name", "sort_order", "number", "id"
            )
        )
    return (
        _base_rooms_qs(event)
        .filter(region_id=region_id)
        .order_by("lodging__sort_order", "lodging__name", "sort_order", "number", "id")
    )


def room_has_vacancy(room: LodgingRoom) -> bool:
    """잔여 객실 여부 — 정원 0(무제한)이거나 활성 배정 인원이 정원 미만."""
    assigned = getattr(room, "assigned_count", None)
    if assigned is None:
        assigned = count_active_occupants_for_room(room)
    return room.capacity == 0 or assigned < room.capacity


def build_lodging_region_tree(
    *,
    all_rooms: Iterable[LodgingRoom],
    visible_groups: Iterable[RetreatGroup],
) -> tuple[list[dict], list[LodgingRoom]]:
    """(region → divisions → rooms) 트리와 미배정 호실 목록을 만든다."""

    rooms_by_key: dict[tuple[int, int], list[LodgingRoom]] = defaultdict(list)
    unassigned_rooms: list[LodgingRoom] = []
    for room in all_rooms:
        if room.region_id is None or room.division_id is None:
            unassigned_rooms.append(room)
        else:
            rooms_by_key[(room.region_id, room.division_id)].append(room)

    group_combos = {
        (g.region_id, g.division_id)
        for g in visible_groups
        if g.region_id is not None and g.division_id is not None
    }
    combo_keys = group_combos | set(rooms_by_key.keys())

    region_ids = {rid for rid, _ in combo_keys}
    division_ids = {did for _, did in combo_keys}
    region_map = {r.id: r for r in Region.objects.filter(id__in=region_ids)}
    division_map = {
        d.id: d
        for d in Division.objects.select_related("region").filter(id__in=division_ids)
    }

    region_buckets: dict[int, dict] = {}
    for region_id, division_id in combo_keys:
        region_obj = region_map.get(region_id)
        division_obj = division_map.get(division_id)
        if region_obj is None or division_obj is None:
            continue
        bucket = region_buckets.setdefault(
            region_id,
            {"region": region_obj, "divisions": []},
        )
        bucket["divisions"].append(
            {
                "division": division_obj,
                "rooms": rooms_by_key.get((region_id, division_id), []),
            }
        )

    for bucket in region_buckets.values():
        bucket["divisions"].sort(
            key=lambda d: (
                d["division"].sort_order or 0,
                d["division"].name,
                d["division"].id,
            )
        )
    regions = sorted(
        region_buckets.values(),
        key=lambda b: (b["region"].sort_order or 0, b["region"].name, b["region"].id),
    )
    return regions, unassigned_rooms
