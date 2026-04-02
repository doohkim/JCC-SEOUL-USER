from django.db import migrations


def rename_periodic_task_label(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    old_name = "attendance.ensure_team_attendance_sessions_next_week"
    new_name = "attendance.ensure_team_attendance_sessions_next_7_days"
    old_qs = PeriodicTask.objects.filter(name=old_name)

    if not old_qs.exists():
        return

    # 이미 새 이름이 있으면 기존(옛 이름)만 제거
    if PeriodicTask.objects.filter(name=new_name).exists():
        old_qs.delete()
        return

    old_qs.update(name=new_name)


def revert_periodic_task_label(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    old_name = "attendance.ensure_team_attendance_sessions_next_week"
    new_name = "attendance.ensure_team_attendance_sessions_next_7_days"
    qs = PeriodicTask.objects.filter(name=new_name)
    if not qs.exists():
        return

    if PeriodicTask.objects.filter(name=old_name).exists():
        qs.delete()
        return

    qs.update(name=old_name)


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0011_periodic_team_attendance_sessions"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(rename_periodic_task_label, revert_periodic_task_label),
    ]

