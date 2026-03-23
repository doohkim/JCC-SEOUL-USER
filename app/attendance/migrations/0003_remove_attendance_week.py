# AttendanceWeek 제거: 출석 행은 division + service_date 직접 참조

from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


def copy_division_from_week(apps, schema_editor):
    Midweek = apps.get_model("attendance", "MidweekAttendanceRecord")
    Sunday = apps.get_model("attendance", "SundayAttendanceLine")
    for r in Midweek.objects.select_related("week").iterator():
        r.division_id = r.week.division_id
        r.save(update_fields=["division_id"])
    for r in Sunday.objects.select_related("week").iterator():
        r.division_id = r.week.division_id
        r.save(update_fields=["division_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0002_worship_service_dates"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="midweekattendancerecord",
            name="division",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="midweek_attendance_records",
                to="users.division",
                verbose_name="부서",
            ),
        ),
        migrations.AddField(
            model_name="sundayattendanceline",
            name="division",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sunday_attendance_lines_division",
                to="users.division",
                verbose_name="부서",
            ),
        ),
        migrations.RunPython(copy_division_from_week, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="midweekattendancerecord",
            name="uniq_midweek_week_member_service",
        ),
        migrations.RemoveConstraint(
            model_name="sundayattendanceline",
            name="uniq_sunday_line_week_member_venue_part_branch",
        ),
        migrations.RemoveField(
            model_name="midweekattendancerecord",
            name="week",
        ),
        migrations.RemoveField(
            model_name="sundayattendanceline",
            name="week",
        ),
        migrations.AlterField(
            model_name="midweekattendancerecord",
            name="division",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="midweek_attendance_records",
                to="users.division",
                verbose_name="부서",
            ),
        ),
        migrations.AlterField(
            model_name="sundayattendanceline",
            name="division",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sunday_attendance_lines_division",
                to="users.division",
                verbose_name="부서",
            ),
        ),
        migrations.AddConstraint(
            model_name="midweekattendancerecord",
            constraint=models.UniqueConstraint(
                fields=("division", "member", "service_type", "service_date"),
                name="uniq_midweek_div_member_service_date",
            ),
        ),
        migrations.AddConstraint(
            model_name="sundayattendanceline",
            constraint=models.UniqueConstraint(
                fields=(
                    "division",
                    "member",
                    "venue",
                    "session_part",
                    "branch_label",
                    "service_date",
                ),
                name="uniq_sunday_div_member_venue_part_branch_date",
            ),
        ),
        migrations.AddIndex(
            model_name="midweekattendancerecord",
            index=models.Index(
                fields=["division", "service_date"],
                name="users_midwe_division_8f1b2d_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="sundayattendanceline",
            index=models.Index(
                fields=["division", "service_date"],
                name="users_sunda_division_9c2e3e_idx",
            ),
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
        migrations.RemoveField(
            model_name="teamattendancesession",
            name="attendance_week",
        ),
        migrations.DeleteModel(
            name="AttendanceWeek",
        ),
    ]
