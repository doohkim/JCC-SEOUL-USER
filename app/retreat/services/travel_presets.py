"""입·퇴실 차량 프리셋 조회·직렬화·웨이브 버킷 매칭."""

from __future__ import annotations

from typing import Any

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


def travel_fixed_and_occurs_map(
    presets: list[RetreatTravelPreset],
) -> tuple[list[RetreatTravelPreset], dict[str, RetreatTravelPreset]]:
    """고정 웨이브 프리셋과 분 단위 시각→프리셋 맵."""
    fixed: list[RetreatTravelPreset] = []
    occurs_to_preset: dict[str, RetreatTravelPreset] = {}
    for p in presets:
        if is_manual_travel_preset(p) or not p.occurs_at:
            continue
        key = _iso_local(p.occurs_at)
        if not key:
            continue
        fixed.append(p)
        # 동일 시각이면 먼저 등록된 프리셋에 귀속
        occurs_to_preset.setdefault(key, p)
    return fixed, occurs_to_preset


def travel_bucket_key(
    dt,
    occurs_to_preset: dict[str, RetreatTravelPreset],
    *,
    is_custom: bool | None = None,
) -> str | int:
    """시각을 웨이브 id / __custom__ / __unset__ 버킷으로 분류.

    ``is_custom=True`` 이면 웨이브 시각과 같아도 자차(``__custom__``).
    ``False``/``None`` 은 기존처럼 분 단위 자동매칭.
    """
    key = _iso_local(dt)
    if not key:
        return "__unset__"
    if is_custom is True:
        return "__custom__"
    matched = occurs_to_preset.get(key)
    if matched is not None:
        return matched.id
    return "__custom__"


def travel_display_label(
    dt,
    occurs_to_preset: dict[str, RetreatTravelPreset],
    *,
    is_custom: bool | None = None,
    custom_label: str = "자차",
) -> str:
    """UI 칩용 짧은 교통 라벨. 시각 없으면 빈 문자열."""
    bucket = travel_bucket_key(dt, occurs_to_preset, is_custom=is_custom)
    if bucket == "__unset__":
        return ""
    if bucket == "__custom__":
        return custom_label
    matched = occurs_to_preset.get(_iso_local(dt))
    if matched is not None and matched.label:
        return matched.label
    for p in occurs_to_preset.values():
        if p.id == bucket and p.label:
            return p.label
    return custom_label


def travel_display_color(
    dt,
    presets: list[RetreatTravelPreset],
    occurs_to_preset: dict[str, RetreatTravelPreset],
    *,
    is_custom: bool | None = None,
) -> str:
    """입력 시각과 매칭된 교통 태그 색상. 미설정이면 빈 문자열."""
    bucket = travel_bucket_key(dt, occurs_to_preset, is_custom=is_custom)
    if bucket == "__unset__":
        return ""
    if bucket == "__custom__":
        manual = next(
            (preset for preset in presets if is_manual_travel_preset(preset)), None
        )
        return manual.color if manual is not None else ""
    matched = next((preset for preset in presets if preset.id == bucket), None)
    return matched.color if matched is not None else ""


def travel_filter_chip_defs(fixed: list[RetreatTravelPreset]) -> list[dict[str, str]]:
    """전체 명단 필터 칩 — value는 str(id) / __custom__ / __unset__."""
    chips: list[dict[str, str]] = [
        {"value": str(p.id), "label": p.label, "color": p.color} for p in fixed
    ]
    chips.append({"value": "__custom__", "label": "자차"})
    chips.append({"value": "__unset__", "label": "미설정"})
    return chips


def travel_column_defs(fixed: list[RetreatTravelPreset]) -> list[dict[str, Any]]:
    """대시보드 교통 집계 컬럼 정의."""
    cols: list[dict[str, Any]] = [
        {
            "id": p.id,
            "code": p.code,
            "label": p.label,
            "color": p.color,
            "manual": False,
        }
        for p in fixed
    ]
    cols.append({"id": None, "code": "__custom__", "label": "자차", "manual": True})
    cols.append({"id": None, "code": "__unset__", "label": "미설정", "manual": False})
    return cols


def serialize_travel_preset(preset: RetreatTravelPreset) -> dict:
    return {
        "id": preset.id,
        "direction": preset.direction,
        "code": preset.code,
        "label": preset.label,
        "color": preset.color,
        "occurs_at": _iso_local(preset.occurs_at),
        "manual": is_manual_travel_preset(preset),
        "sort_order": preset.sort_order,
    }


def travel_preset_models_for_group(
    group: RetreatGroup,
) -> dict[str, list[RetreatTravelPreset]]:
    """조 division(주 + 추가 스코프)에 맞는 활성 프리셋 모델."""
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
    arrival: list[RetreatTravelPreset] = []
    departure: list[RetreatTravelPreset] = []
    for preset in qs:
        preset_div_ids = {d.id for d in preset.divisions.all()}
        if preset_div_ids and division_ids and preset_div_ids.isdisjoint(division_ids):
            continue
        if preset_div_ids and not division_ids:
            continue
        if preset.direction == RetreatTravelPreset.Direction.ARRIVAL:
            arrival.append(preset)
        else:
            departure.append(preset)
    return {"arrival": arrival, "departure": departure}


def travel_presets_for_group(group: RetreatGroup) -> dict[str, list[dict]]:
    """조 division(주 + 추가 스코프)에 맞는 활성 프리셋."""
    models = travel_preset_models_for_group(group)
    return {
        "arrival": [serialize_travel_preset(p) for p in models["arrival"]],
        "departure": [serialize_travel_preset(p) for p in models["departure"]],
    }


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
