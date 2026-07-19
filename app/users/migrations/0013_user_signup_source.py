"""User.signup_source 추가 및 기존 계정 백필."""

from django.conf import settings
from django.db import migrations, models


def backfill_signup_source(apps, schema_editor):
    User = apps.get_model("users", "User")
    UserSocialAuth = apps.get_model("social_django", "UserSocialAuth")

    kakao_user_ids = set(
        UserSocialAuth.objects.filter(provider="kakao").values_list(
            "user_id", flat=True
        )
    )
    seed_usernames = set(getattr(settings, "DEFAULT_USERS", {}).keys())

    to_update = []
    for user in User.objects.all().only("id", "username", "signup_source"):
        if user.id in kakao_user_ids or (user.username or "").startswith("kakao_"):
            source = "kakao"
        elif user.username in seed_usernames:
            source = "seed"
        else:
            source = "admin"
        if user.signup_source != source:
            user.signup_source = source
            to_update.append(user)

    if to_update:
        User.objects.bulk_update(to_update, ["signup_source"], batch_size=500)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("social_django", "__first__"),
        ("users", "0012_preserve_profile_on_user_delete"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="signup_source",
            field=models.CharField(
                choices=[
                    ("kakao", "카카오 가입"),
                    ("seed", "시드 계정"),
                    ("admin", "관리자 생성"),
                ],
                db_index=True,
                default="admin",
                max_length=16,
                verbose_name="가입 경로",
            ),
        ),
        migrations.RunPython(backfill_signup_source, noop_reverse),
    ]
