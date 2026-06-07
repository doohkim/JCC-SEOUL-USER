# Generated manually for counselor -> pastor rename

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("counseling", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameModel(
            old_name="CounselorScheduleSettings",
            new_name="PastorScheduleSettings",
        ),
        migrations.RenameModel(
            old_name="CounselorDayOverride",
            new_name="PastorDayOverride",
        ),
        migrations.AlterField(
            model_name="pastorschedulesettings",
            name="user",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pastor_schedule_settings",
                to=settings.AUTH_USER_MODEL,
                verbose_name="목회자",
            ),
        ),
        migrations.AlterModelOptions(
            name="pastorschedulesettings",
            options={
                "verbose_name": "목회자 일정 템플릿",
                "verbose_name_plural": "목회자 일정 템플릿",
            },
        ),
        migrations.AlterModelOptions(
            name="pastordayoverride",
            options={
                "verbose_name": "목회자 일별 예약 오버라이드",
                "verbose_name_plural": "목회자 일별 예약 오버라이드",
            },
        ),
        migrations.RemoveConstraint(
            model_name="pastordayoverride",
            name="unique_counselor_day_override",
        ),
        migrations.RenameField(
            model_name="pastordayoverride",
            old_name="counselor",
            new_name="pastor",
        ),
        migrations.AlterField(
            model_name="pastordayoverride",
            name="pastor",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pastor_day_overrides",
                to=settings.AUTH_USER_MODEL,
                verbose_name="목회자",
            ),
        ),
        migrations.AddConstraint(
            model_name="pastordayoverride",
            constraint=models.UniqueConstraint(
                fields=("pastor", "date"),
                name="unique_pastor_day_override",
            ),
        ),
        migrations.RemoveIndex(
            model_name="counselingslot",
            name="counseling__counsel_211739_idx",
        ),
        migrations.RemoveConstraint(
            model_name="counselingslot",
            name="unique_counselor_date_start",
        ),
        migrations.RenameField(
            model_name="counselingslot",
            old_name="counselor",
            new_name="pastor",
        ),
        migrations.AlterField(
            model_name="counselingslot",
            name="pastor",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="counseling_slots",
                to=settings.AUTH_USER_MODEL,
                verbose_name="목회자",
            ),
        ),
        migrations.AddConstraint(
            model_name="counselingslot",
            constraint=models.UniqueConstraint(
                fields=("pastor", "date", "start_time"),
                name="unique_pastor_date_start",
            ),
        ),
        migrations.AddIndex(
            model_name="counselingslot",
            index=models.Index(
                fields=["pastor", "date", "state"],
                name="counseling__pastor_211739_idx",
            ),
        ),
        migrations.RemoveIndex(
            model_name="counselingrequest",
            name="counseling__counsel_21aad3_idx",
        ),
        migrations.RenameField(
            model_name="counselingrequest",
            old_name="counselor",
            new_name="pastor",
        ),
        migrations.AlterField(
            model_name="counselingrequest",
            name="pastor",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="counseling_requests_received",
                to=settings.AUTH_USER_MODEL,
                verbose_name="목회자",
            ),
        ),
        migrations.RenameField(
            model_name="counselingrequest",
            old_name="counselor_notes_json",
            new_name="pastor_notes_json",
        ),
        migrations.AddIndex(
            model_name="counselingrequest",
            index=models.Index(
                fields=["pastor", "status"],
                name="counseling__pastor_21aad3_idx",
            ),
        ),
    ]
