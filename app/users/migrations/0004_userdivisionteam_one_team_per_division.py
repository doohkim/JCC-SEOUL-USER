# Generated manually: one UserDivisionTeam row per (user, division).

from django.db import migrations, models
from django.db.models import Count


def dedupe_user_division_teams(apps, schema_editor):
    UDT = apps.get_model("users", "UserDivisionTeam")
    dup_groups = (
        UDT.objects.values("user_id", "division_id")
        .annotate(c=Count("id"))
        .filter(c__gt=1)
    )
    for g in dup_groups:
        rows = list(
            UDT.objects.filter(
                user_id=g["user_id"],
                division_id=g["division_id"],
            ).order_by("-is_primary", "sort_order", "id")
        )
        if len(rows) <= 1:
            continue
        for r in rows[1:]:
            r.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_pastoraldivisionassignment"),
    ]

    operations = [
        migrations.RunPython(dedupe_user_division_teams, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="userdivisionteam",
            name="unique_user_division_team",
        ),
        migrations.AddConstraint(
            model_name="userdivisionteam",
            constraint=models.UniqueConstraint(
                fields=("user", "division"),
                name="unique_users_user_division",
            ),
        ),
    ]
