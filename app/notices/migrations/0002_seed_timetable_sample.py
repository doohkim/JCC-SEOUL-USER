"""타임테이블 샘플 일정 시드."""

from __future__ import annotations

import datetime

from django.db import migrations


def seed_timetable(apps, schema_editor):
    TimetableEntry = apps.get_model("notices", "TimetableEntry")
    if TimetableEntry.objects.exists():
        return
    day1 = datetime.date(2026, 6, 2)
    day2 = datetime.date(2026, 6, 3)
    TimetableEntry.objects.bulk_create(
        [
            TimetableEntry(
                day=day1,
                start_time=datetime.time(9, 0),
                end_time=datetime.time(10, 0),
                title="입회 · 오리엔테이션",
                location="본관 로비",
                description="짐 보관 및 조 배정 안내",
                sort_order=1,
            ),
            TimetableEntry(
                day=day1,
                start_time=datetime.time(12, 0),
                end_time=datetime.time(13, 30),
                title="점심식사",
                location="식당",
                description="",
                sort_order=2,
            ),
            TimetableEntry(
                day=day2,
                start_time=datetime.time(19, 0),
                end_time=datetime.time(21, 0),
                title="저녁 집회",
                location="예배당",
                description="본 집회 프로그램",
                sort_order=1,
            ),
        ]
    )


def unseed_timetable(apps, schema_editor):
    TimetableEntry = apps.get_model("notices", "TimetableEntry")
    TimetableEntry.objects.filter(
        title__in=[
            "입회 · 오리엔테이션",
            "점심식사",
            "저녁 집회",
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("notices", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_timetable, unseed_timetable),
    ]
