# Generated manually for staff application track

from django.db import migrations, models


def backfill_application_track(apps, schema_editor):
    RetreatStaffApplication = apps.get_model("retreat", "RetreatStaffApplication")
    for app in RetreatStaffApplication.objects.all().iterator():
        if app.group_id and app.group_role:
            track = "group_leadership"
        else:
            track = "council"
        if app.application_track != track:
            app.application_track = track
            app.save(update_fields=["application_track"])


class Migration(migrations.Migration):

    dependencies = [
        ("retreat", "0039_staff_application"),
    ]

    operations = [
        migrations.AddField(
            model_name="retreatstaffapplication",
            name="application_track",
            field=models.CharField(
                blank=True,
                choices=[
                    ("council", "집회 운영진"),
                    ("group_leadership", "조장·부조장"),
                ],
                default="",
                max_length=24,
                verbose_name="신청 유형",
            ),
        ),
        migrations.RunPython(backfill_application_track, migrations.RunPython.noop),
    ]
