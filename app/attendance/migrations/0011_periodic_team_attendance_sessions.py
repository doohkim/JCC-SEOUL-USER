# Generated manually for django-celery-beat periodic task

from django.db import migrations


def create_periodic_task(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="3",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="Asia/Seoul",
    )
    PeriodicTask.objects.update_or_create(
        name="attendance.ensure_team_attendance_sessions_next_week",
        defaults={
            "task": "attendance.tasks.ensure_team_attendance_sessions_next_week",
            "crontab": schedule,
            "interval": None,
            "enabled": True,
        },
    )


def remove_periodic_task(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(
        name="attendance.ensure_team_attendance_sessions_next_week"
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0010_rename_attendance_p_division_2f4c8e_idx_attendance__divisio_14bd69_idx"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(create_periodic_task, remove_periodic_task),
    ]
