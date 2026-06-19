from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0015_user_can_manage_notices"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="avatar_user_uploaded",
            field=models.BooleanField(
                default=False,
                help_text="프로필 페이지에서 직접 올린 이미지만 화면에 표시한다.",
                verbose_name="사용자 업로드 프로필 이미지",
            ),
        ),
    ]
