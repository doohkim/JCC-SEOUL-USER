"""Lodging.region FK 추가 (지역 태깅, nullable=전 지역 공용)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("retreat", "0013_lodging_models"),
        ("users", "0009_region_and_division_region"),
    ]

    operations = [
        migrations.AddField(
            model_name="lodging",
            name="region",
            field=models.ForeignKey(
                blank=True,
                help_text="비워두면 전 지역 공용 숙소로 처리됩니다.",
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="retreat_lodgings",
                to="users.region",
                verbose_name="지역",
            ),
        ),
    ]
