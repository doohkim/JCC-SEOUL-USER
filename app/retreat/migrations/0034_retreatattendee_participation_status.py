from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("retreat", "0033_retreattimetableentry_end_day"),
    ]

    operations = [
        migrations.AddField(
            model_name="retreatattendee",
            name="participation_status",
            field=models.CharField(
                choices=[("participating", "참석"), ("absent", "불참")],
                default="participating",
                help_text="불참으로 표시된 조원은 입·퇴실·숙소·픽업 집계에서 제외됩니다.",
                max_length=15,
                verbose_name="참석 여부",
            ),
        ),
    ]
