"""기존 RetreatGroup.order 백필.

`order == 0` 인 행에 한해, `name`의 앞자리 숫자(예: '1조' → 1, '10조' → 10)
를 추출해 order로 채워준다.
"""

from __future__ import annotations

import re

from django.db import migrations


_LEADING = re.compile(r"^\s*(\d+)")


def backfill(apps, schema_editor):
    RetreatGroup = apps.get_model("retreat", "RetreatGroup")
    for group in RetreatGroup.objects.filter(order=0):
        m = _LEADING.match(group.name or "")
        if m:
            group.order = int(m.group(1))
            group.save(update_fields=["order"])


class Migration(migrations.Migration):

    dependencies = [
        ("retreat", "0003_retreat_council"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
