from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_user_permission_flags_and_rolelevel_remap"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="rolelevel",
            options={"ordering": ["-level", "sort_order"], "verbose_name": "직급", "verbose_name_plural": "직급"},
        ),
        migrations.AlterField(
            model_name="rolelevel",
            name="level",
            field=models.PositiveSmallIntegerField(default=0, help_text="숫자 클수록 상위 직급", verbose_name="레벨"),
        ),
    ]
