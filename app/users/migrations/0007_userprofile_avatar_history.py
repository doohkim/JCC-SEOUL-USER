from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0006_alter_rolelevel_options_alter_rolelevel_level"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserProfileAvatar",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "image",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="users/avatars/",
                        verbose_name="프로필 이미지(히스토리)",
                    ),
                ),
                (
                    "source_url",
                    models.URLField(blank=True, null=True, verbose_name="원본 URL"),
                ),
                (
                    "content_hash",
                    models.CharField(
                        db_index=True,
                        max_length=64,
                        verbose_name="이미지 콘텐츠 해시(sha256 hex)",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user_profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="avatar_history",
                        to="users.userprofile",
                        verbose_name="프로필",
                    ),
                ),
            ],
            options={
                "db_table": "users_userprofileavatar",
                "verbose_name": "사용자 프로필 이미지(히스토리)",
                "verbose_name_plural": "사용자 프로필 이미지(히스토리)",
            },
        ),
        migrations.AddConstraint(
            model_name="userprofileavatar",
            constraint=models.UniqueConstraint(
                fields=("user_profile", "content_hash"),
                name="uniq_userprofile_avatar_content_hash",
            ),
        ),
    ]

