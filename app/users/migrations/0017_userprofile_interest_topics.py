from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0016_userprofile_avatar_user_uploaded"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="interest_topics",
            field=models.CharField(
                blank=True,
                default="",
                help_text="쉼표로 구분된 관심 주제 태그",
                max_length=500,
                verbose_name="관심 주제",
            ),
        ),
    ]
