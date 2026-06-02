# Generated manually for retreat attendance snapshot FK switch.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("retreat", "0008_backfill_session_enrollments"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="retreatattendance",
            name="uniq_retreat_attendance_attendee_session",
        ),
        migrations.RemoveIndex(
            model_name="retreatattendance",
            name="idx_retreat_att_session_status",
        ),
        migrations.AlterField(
            model_name="retreatattendance",
            name="enrollment",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="attendance",
                to="retreat.retreatsessionattendee",
                verbose_name="출석부 조원",
            ),
        ),
        migrations.RemoveField(
            model_name="retreatattendance",
            name="attendee",
        ),
        migrations.RemoveField(
            model_name="retreatattendance",
            name="session",
        ),
        migrations.AddIndex(
            model_name="retreatattendance",
            index=models.Index(fields=["status"], name="idx_retreat_att_status"),
        ),
    ]
