from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("retreat", "0048_lodging_room_targets"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lodgingroom",
            name="recommended_gender",
            field=models.CharField(
                blank=True,
                choices=[("male", "남성"), ("female", "여성"), ("", "미지정")],
                default="",
                help_text=(
                    "남성 또는 여성을 반드시 지정합니다. "
                    "빈 값은 기존 미설정 호실 호환용입니다."
                ),
                max_length=10,
                verbose_name="성별",
            ),
        ),
    ]
