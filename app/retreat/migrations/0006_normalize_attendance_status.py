"""기존 'late' / 'excused' 출석 상태를 정리.

이제 RetreatAttendance.Status 는 present / absent 두 가지뿐이므로,
- 'late'   → 'present' (지각도 출석으로 간주)
- 'excused'→ 'absent'  (사유 결석)
로 변환한다.
"""

from __future__ import annotations

from django.db import migrations


def normalize(apps, schema_editor):
    RetreatAttendance = apps.get_model("retreat", "RetreatAttendance")
    RetreatAttendance.objects.filter(status="late").update(status="present")
    RetreatAttendance.objects.filter(status="excused").update(status="absent")


class Migration(migrations.Migration):

    dependencies = [
        ("retreat", "0005_alter_retreatattendee_options_and_more"),
    ]

    operations = [
        migrations.RunPython(normalize, migrations.RunPython.noop),
    ]
