"""청년·대학부 입퇴실 차량 프리셋 시드 (2026 하계수련회 시간표 기준)."""

from __future__ import annotations

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from retreat.models import RetreatEvent, RetreatTravelPreset
from users.models import Division

# (direction, code, label, occurs_at local naive, sort_order)
_YOUTH_UNIVERSITY_PRESETS = [
    (
        RetreatTravelPreset.Direction.ARRIVAL,
        "advance",
        "7/29 선발대",
        datetime(2026, 7, 29, 23, 0),
        10,
    ),
    (
        RetreatTravelPreset.Direction.ARRIVAL,
        "main",
        "7/30 본진",
        datetime(2026, 7, 30, 10, 0),
        20,
    ),
    (
        RetreatTravelPreset.Direction.ARRIVAL,
        "late",
        "7/30 후발대",
        datetime(2026, 7, 30, 21, 0),
        30,
    ),
    (
        RetreatTravelPreset.Direction.ARRIVAL,
        "own_car_730",
        "7/30 자차",
        datetime(2026, 7, 30, 10, 0),
        40,
    ),
    (
        RetreatTravelPreset.Direction.ARRIVAL,
        "day_731",
        "7/31",
        datetime(2026, 7, 31, 10, 0),
        50,
    ),
    (
        RetreatTravelPreset.Direction.ARRIVAL,
        "day_801",
        "8/1",
        datetime(2026, 8, 1, 10, 0),
        60,
    ),
    (
        RetreatTravelPreset.Direction.DEPARTURE,
        "bus_after_evening_731",
        "7/31 저녁집회 후 버스",
        datetime(2026, 7, 31, 22, 0),
        10,
    ),
    (
        RetreatTravelPreset.Direction.DEPARTURE,
        "own_car_731",
        "7/31 자차",
        datetime(2026, 7, 31, 13, 0),
        20,
    ),
    (
        RetreatTravelPreset.Direction.DEPARTURE,
        "bus_dawn_801",
        "8/1 새벽 버스",
        datetime(2026, 8, 1, 2, 0),
        30,
    ),
    (
        RetreatTravelPreset.Direction.DEPARTURE,
        "bus_801",
        "8/1 버스",
        datetime(2026, 8, 1, 13, 0),
        40,
    ),
    (
        RetreatTravelPreset.Direction.DEPARTURE,
        "own_car_801",
        "8/1 자차",
        datetime(2026, 8, 1, 13, 0),
        50,
    ),
]


class Command(BaseCommand):
    help = "집회에 청년·대학부 입퇴실 차량 프리셋을 시드합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--event-id",
            type=int,
            required=True,
            help="대상 집회 ID",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="해당 집회의 기존 프리셋을 지우고 다시 넣습니다.",
        )

    def handle(self, *args, **options):
        event_id = options["event_id"]
        event = RetreatEvent.objects.filter(pk=event_id).first()
        if event is None:
            raise CommandError(f"집회 id={event_id} 를 찾을 수 없습니다.")

        divisions = list(
            Division.objects.filter(code__in=["youth", "university"]).order_by(
                "sort_order", "id"
            )
        )
        if not divisions:
            # 코드가 다른 환경: 이름에 청년부/대학부 포함
            divisions = list(
                Division.objects.filter(name__in=["청년부", "대학부"]).order_by(
                    "sort_order", "id"
                )
            )
        if not divisions:
            raise CommandError(
                "청년부·대학부 Division 을 찾지 못했습니다 (code=youth|university)."
            )

        if options["replace"]:
            deleted, _ = RetreatTravelPreset.objects.filter(event=event).delete()
            self.stdout.write(f"기존 프리셋 {deleted}건 삭제")

        tz = timezone.get_current_timezone()
        created = 0
        updated = 0
        for direction, code, label, naive_dt, sort_order in _YOUTH_UNIVERSITY_PRESETS:
            occurs_at = timezone.make_aware(naive_dt, tz)
            obj, was_created = RetreatTravelPreset.objects.update_or_create(
                event=event,
                direction=direction,
                code=code,
                defaults={
                    "label": label,
                    "occurs_at": occurs_at,
                    "sort_order": sort_order,
                    "is_active": True,
                },
            )
            obj.divisions.set(divisions)
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{event.name}: 생성 {created}, 갱신 {updated} "
                f"(부서 {[d.name for d in divisions]})"
            )
        )
