# Generated manually for retreat session snapshot backfill.

from django.db import migrations


def forwards(apps, schema_editor):
    RetreatSession = apps.get_model("retreat", "RetreatSession")
    RetreatAttendee = apps.get_model("retreat", "RetreatAttendee")
    RetreatSessionAttendee = apps.get_model("retreat", "RetreatSessionAttendee")
    RetreatAttendance = apps.get_model("retreat", "RetreatAttendance")

    session_qs = RetreatSession.objects.all().only("id", "event_id")
    for session in session_qs.iterator():
        attendees = (
            RetreatAttendee.objects.filter(group__event_id=session.event_id)
            .select_related("group", "group__region", "group__division")
            .order_by(
                "group__region__sort_order",
                "group__division__sort_order",
                "group__order",
                "sort_order",
                "name",
                "id",
            )
        )
        for attendee in attendees.iterator():
            group = attendee.group
            RetreatSessionAttendee.objects.get_or_create(
                session_id=session.id,
                source_attendee_id=attendee.id,
                defaults={
                    "source_group_id": group.id,
                    "name": attendee.name,
                    "phone": attendee.phone,
                    "gender": attendee.gender,
                    "memo": attendee.memo,
                    "check_in_status": getattr(attendee, "check_in_status", "checked_in"),
                    "group_name": group.name,
                    "region_id_snapshot": group.region_id,
                    "region_name": getattr(group.region, "name", "") or "",
                    "division_id_snapshot": group.division_id,
                    "division_name": getattr(group.division, "name", "") or "",
                    "sort_order": attendee.sort_order,
                },
            )

    for attendance in RetreatAttendance.objects.all().iterator():
        enrollment = RetreatSessionAttendee.objects.filter(
            session_id=attendance.session_id,
            source_attendee_id=attendance.attendee_id,
        ).first()
        if enrollment is None:
            continue
        attendance.enrollment_id = enrollment.id
        attendance.save(update_fields=["enrollment"])


def backwards(apps, schema_editor):
    RetreatAttendance = apps.get_model("retreat", "RetreatAttendance")
    RetreatSessionAttendee = apps.get_model("retreat", "RetreatSessionAttendee")
    RetreatAttendance.objects.update(enrollment=None)
    RetreatSessionAttendee.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("retreat", "0007_session_status_enrollment"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
