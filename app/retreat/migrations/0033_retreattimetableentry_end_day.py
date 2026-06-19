from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("retreat", "0032_rename_event_verbose_names_to_gathering"),
    ]

    operations = [
        migrations.AddField(
            model_name="retreattimetableentry",
            name="end_day",
            field=models.DateField(
                blank=True,
                help_text="종료 시각이 시작 일자와 다를 때만 설정(자정 넘김 등). 비우면 시작 일자와 동일.",
                null=True,
                verbose_name="종료 일자",
            ),
        ),
    ]
