from django.db import migrations, models


def forwards_fill_team_snapshot(apps, schema_editor):
    Sunday = apps.get_model("attendance", "SundayAttendanceLine")
    Midweek = apps.get_model("attendance", "MidweekAttendanceRecord")

    for row in Sunday.objects.select_related("team").all().iterator():
        if row.team_id:
            row.team_name_snapshot = (row.team.name or "")[:100]
            row.save(update_fields=["team_name_snapshot"])

    for row in Midweek.objects.select_related("team").all().iterator():
        if row.team_id:
            row.team_name_snapshot = (row.team.name or "")[:100]
            row.save(update_fields=["team_name_snapshot"])


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0004_midweek_team_field"),
    ]

    operations = [
        migrations.AddField(
            model_name="midweekattendancerecord",
            name="team_name_snapshot",
            field=models.CharField(
                blank=True,
                default="",
                help_text="출석 등록 당시의 팀명. 이후 소속 변경과 무관하게 유지.",
                max_length=100,
                verbose_name="팀명 스냅샷",
            ),
        ),
        migrations.AddField(
            model_name="sundayattendanceline",
            name="team_name_snapshot",
            field=models.CharField(
                blank=True,
                default="",
                help_text="출석 등록 당시의 팀명. 이후 소속 변경과 무관하게 유지.",
                max_length=100,
                verbose_name="팀명 스냅샷",
            ),
        ),
        migrations.RunPython(
            forwards_fill_team_snapshot,
            migrations.RunPython.noop,
        ),
    ]

