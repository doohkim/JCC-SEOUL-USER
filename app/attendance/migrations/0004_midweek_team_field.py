from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
        ("attendance", "0003_remove_attendance_week"),
    ]

    operations = [
        migrations.AddField(
            model_name="midweekattendancerecord",
            name="team",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="midweek_attendance_records",
                to="users.team",
                verbose_name="팀",
            ),
        ),
    ]

