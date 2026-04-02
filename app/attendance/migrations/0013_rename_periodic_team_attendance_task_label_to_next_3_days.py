from django.db import migrations


def rename_periodic_task_label_to_next_3_days(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    new_name = "attendance.ensure_team_attendance_sessions_next_3_days"
    old_names = [
        "attendance.ensure_team_attendance_sessions_next_week",
        "attendance.ensure_team_attendance_sessions_next_7_days",
    ]

    existing_new = PeriodicTask.objects.filter(name=new_name)
    if existing_new.exists():
        PeriodicTask.objects.filter(name__in=old_names).delete()
        return

    qs = list(PeriodicTask.objects.filter(name__in=old_names).order_by("id"))
    if not qs:
        return

    keep = qs[0]
    keep.name = new_name
    keep.save(update_fields=["name"])
    for extra in qs[1:]:
        extra.delete()


def revert_periodic_task_label(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    new_name = "attendance.ensure_team_attendance_sessions_next_3_days"
    old_names = [
        "attendance.ensure_team_attendance_sessions_next_week",
        "attendance.ensure_team_attendance_sessions_next_7_days",
    ]

    qs = list(PeriodicTask.objects.filter(name=new_name).order_by("id"))
    if not qs:
        return

    existing_old = PeriodicTask.objects.filter(name__in=old_names)
    if existing_old.exists():
        PeriodicTask.objects.filter(name=new_name).delete()
        return

    keep = qs[0]
    keep.name = old_names[1]  # revert 기본: next_7_days
    keep.save(update_fields=["name"])
    for extra in qs[1:]:
        extra.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0012_rename_periodic_team_attendance_task_label"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(
            rename_periodic_task_label_to_next_3_days,
            revert_periodic_task_label,
        ),
    ]

