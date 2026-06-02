# Generated manually for retreat attendance meta and changelog target choices.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("retreat", "0009_attendance_use_enrollment"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="retreatattendance",
            options={
                "ordering": ["enrollment__session", "enrollment"],
                "verbose_name": "수련회 출석",
                "verbose_name_plural": "수련회 출석",
            },
        ),
        migrations.AlterField(
            model_name="retreatchangelog",
            name="target_type",
            field=models.CharField(
                choices=[
                    ("session", "출석부"),
                    ("attendee", "조원"),
                    ("enrollment", "출석부 조원"),
                    ("attendance", "출석"),
                    ("group_membership", "조 운영진"),
                    ("group", "조"),
                ],
                max_length=30,
                verbose_name="대상 유형",
            ),
        ),
    ]
