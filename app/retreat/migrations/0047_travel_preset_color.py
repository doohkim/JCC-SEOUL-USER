from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("retreat", "0046_remove_periodic_auto_check_in"),
    ]

    operations = [
        migrations.AddField(
            model_name="retreattravelpreset",
            name="color",
            field=models.CharField(
                default="#2563EB",
                help_text="Admin 컬러 피커에서 선택하는 프리셋 태그 색상.",
                max_length=7,
                validators=[
                    django.core.validators.RegexValidator(
                        message="#2563EB 형식의 HEX 색상을 입력하세요.",
                        regex="^#[0-9A-Fa-f]{6}$",
                    )
                ],
                verbose_name="색상",
            ),
        ),
    ]
