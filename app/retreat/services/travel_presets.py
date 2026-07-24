"""입·퇴실 차량 프리셋 조회·직렬화."""

from __future__ import annotations

from django.utils import timezone

from retreat.models import RetreatEvent, RetreatGroup, RetreatTravelPreset


def _iso_local(dt) -> str:
    if dt is None:
        return ""
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return timezone.localtime(dt).strftime("%Y-%m-%dT%H:%M")


def is_manual_travel_preset(preset: RetreatTravelPreset) -> bool:
    """자차 등 — 고정 시각 없이 달력에서 직접 입력."""
    code = (preset.code or "").lower()
    label = preset.label or ""
    return "own_car" in code or "자차" in label


def serialize_travel_preset(preset: RetreatTravelPreset) -> dict:
    return {
        "id": preset.id,
        "direction": preset.direction,
        "code": preset.code,
        "label": preset.label,
        "occurs_at": _iso_local(preset.occurs_at),
        "manual": is_manual_travel_preset(preset),
        "sort_order": preset.sort_order,
    }


def travel_presets_for_group(group: RetreatGroup) -> dict[str, list[dict]]:
    """조 division(주 + 추가 스코프)에 맞는 활성 프리셋."""
    event = group.event
    division_ids = set()
    if group.division_id:
        division_ids.add(group.division_id)
    for scope in group.extra_scopes.all():
        if scope.division_id:
            division_ids.add(scope.division_id)

    qs = (
        RetreatTravelPreset.objects.filter(event=event, is_active=True)
        .prefetch_related("divisions")
        .order_by("direction", "sort_order", "id")
    )
    arrival: list[dict] = []
    departure: list[dict] = []
    for preset in qs:
        preset_div_ids = {d.id for d in preset.divisions.all()}
        if preset_div_ids and division_ids and preset_div_ids.isdisjoint(division_ids):
            continue
        if preset_div_ids and not division_ids:
            continue
        row = serialize_travel_preset(preset)
        if preset.direction == RetreatTravelPreset.Direction.ARRIVAL:
            arrival.append(row)
        else:
            departure.append(row)
    return {"arrival": arrival, "departure": departure}


def travel_presets_for_event(event: RetreatEvent) -> dict[str, list[dict]]:
    qs = RetreatTravelPreset.objects.filter(event=event, is_active=True).order_by(
        "direction", "sort_order", "id"
    )
    arrival = []
    departure = []
    for preset in qs:
        row = serialize_travel_preset(preset)
        if preset.direction == RetreatTravelPreset.Direction.ARRIVAL:
            arrival.append(row)
        else:
            departure.append(row)
    return {"arrival": arrival, "departure": departure}
