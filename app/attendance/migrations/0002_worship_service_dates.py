# Generated manually: 예배일(service_date) + 백필

from __future__ import annotations

from datetime import timedelta

from django.db import migrations, models


def backfill_service_dates(apps, schema_editor):
    Midweek = apps.get_model("attendance", "MidweekAttendanceRecord")
    Sunday = apps.get_model("attendance", "SundayAttendanceLine")

    for r in Midweek.objects.select_related("week").iterator():
        ws = r.week.week_sunday
        if r.service_type == "wednesday":
            r.service_date = ws + timedelta(days=3)
        else:
            r.service_date = ws + timedelta(days=6)
        r.save(update_fields=["service_date"])

    for r in Sunday.objects.select_related("week").iterator():
        r.service_date = r.week.week_sunday
        r.save(update_fields=["service_date"])


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="midweekattendancerecord",
            name="service_date",
            field=models.DateField(
                help_text="실제 수요·토요 예배가 열린 날짜.",
                null=True,
                verbose_name="예배일",
            ),
        ),
        migrations.AddField(
            model_name="sundayattendanceline",
            name="service_date",
            field=models.DateField(
                help_text="해당 주일 예배가 열린 날짜(시트 상 날짜).",
                null=True,
                verbose_name="주일 예배일",
            ),
        ),
        migrations.RunPython(backfill_service_dates, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="midweekattendancerecord",
            name="service_date",
            field=models.DateField(
                help_text="실제 수요·토요 예배가 열린 날짜.",
                verbose_name="예배일",
            ),
        ),
        migrations.AlterField(
            model_name="sundayattendanceline",
            name="service_date",
            field=models.DateField(
                help_text="해당 주일 예배가 열린 날짜(시트 상 날짜).",
                verbose_name="주일 예배일",
            ),
        ),
        migrations.AlterField(
            model_name="midweekattendancerecord",
            name="week",
            field=models.ForeignKey(
                help_text="예배일이 속한 주의 기준 주일과 맞는 ``AttendanceWeek`` 행입니다.",
                on_delete=models.deletion.CASCADE,
                related_name="midweek_records",
                to="attendance.attendanceweek",
                verbose_name="연결 주차(내부)",
            ),
        ),
        migrations.AlterField(
            model_name="sundayattendanceline",
            name="week",
            field=models.ForeignKey(
                help_text="주일 예배일이 속한 주의 기준 주일과 맞는 ``AttendanceWeek`` 행입니다.",
                on_delete=models.deletion.CASCADE,
                related_name="sunday_lines",
                to="attendance.attendanceweek",
                verbose_name="연결 주차(내부)",
            ),
        ),
        migrations.AlterModelOptions(
            name="attendanceweek",
            options={
                "ordering": ["-week_sunday", "division"],
                "verbose_name": "출석 주차 (부서·기준주일·내부키)",
                "verbose_name_plural": "출석 주차 (부서·기준주일·내부키)",
            },
        ),
        migrations.AlterModelOptions(
            name="midweekattendancerecord",
            options={
                "ordering": ["-service_date", "service_type", "member__name"],
                "verbose_name": "수요·토요 출석",
                "verbose_name_plural": "수요·토요 출석",
            },
        ),
        migrations.AlterModelOptions(
            name="sundayattendanceline",
            options={
                "ordering": ["-service_date", "member__name", "venue", "session_part"],
                "verbose_name": "주일 출석(행)",
                "verbose_name_plural": "주일 출석(행)",
            },
        ),
    ]
