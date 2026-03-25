# Generated manually: one MemberDivisionTeam row per (member, division).

from django.db import migrations, models
from django.db.models import Count


def dedupe_member_division_teams(apps, schema_editor):
    MDT = apps.get_model("registry", "MemberDivisionTeam")
    dup_groups = (
        MDT.objects.values("member_id", "division_id")
        .annotate(c=Count("id"))
        .filter(c__gt=1)
    )
    for g in dup_groups:
        rows = list(
            MDT.objects.filter(
                member_id=g["member_id"],
                division_id=g["division_id"],
            ).order_by("-is_primary", "sort_order", "id")
        )
        if len(rows) <= 1:
            continue
        for r in rows[1:]:
            r.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("registry", "0002_alter_member_linked_user_and_more"),
    ]

    operations = [
        migrations.RunPython(dedupe_member_division_teams, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="memberdivisionteam",
            name="unique_member_division_team",
        ),
        migrations.AddConstraint(
            model_name="memberdivisionteam",
            constraint=models.UniqueConstraint(
                fields=("member", "division"),
                name="unique_registry_member_division",
            ),
        ),
    ]
