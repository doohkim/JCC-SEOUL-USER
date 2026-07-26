from django.db import migrations


TASK_NAME = "retreat.auto_transition_check_in"


def remove_periodic_task(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=TASK_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("retreat", "0045_attendee_manual_status_and_auto_indexes"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(remove_periodic_task, migrations.RunPython.noop),
    ]
