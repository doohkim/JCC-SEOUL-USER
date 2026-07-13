"""조원 없이 남은 픽업(탈퇴 등)을 account_retired_at 으로 마킹."""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from retreat.models import RetreatAttendee, RetreatPickup


class Command(BaseCommand):
    help = (
        "조원 명단에 없는 픽업을 탈퇴 잔존 데이터로 마킹합니다. "
        "일반 조회 목록에서 숨김 처리됩니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--event-id",
            type=int,
            help="특정 집회만 처리 (미지정 시 전체)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="변경 없이 대상만 출력",
        )

    def handle(self, *args, **options):
        event_id = options.get("event_id")
        dry_run = bool(options.get("dry_run"))
        qs = RetreatPickup.objects.filter(
            account_retired_at__isnull=True,
            group_id__isnull=False,
        ).select_related("event", "group")
        if event_id:
            qs = qs.filter(event_id=event_id)

        attendee_keys = set(
            RetreatAttendee.objects.filter(
                group_id__in=qs.values_list("group_id", flat=True).distinct()
            ).values_list("group_id", "name")
        )

        marked = 0
        retired_at = timezone.now()
        for pickup in qs.iterator():
            key = (pickup.group_id, pickup.name)
            if key in attendee_keys:
                continue
            marked += 1
            label = (
                f"pickup#{pickup.id} {pickup.event.name} "
                f"{pickup.get_direction_display()} {pickup.name}"
            )
            if dry_run:
                self.stdout.write(f"[dry-run] {label}")
                continue
            pickup.account_retired_at = retired_at
            pickup.save(update_fields=["account_retired_at", "updated_at"])
            self.stdout.write(f"marked {label}")

        suffix = " (dry-run)" if dry_run else ""
        self.stdout.write(self.style.SUCCESS(f"done: {marked} pickup(s){suffix}"))
