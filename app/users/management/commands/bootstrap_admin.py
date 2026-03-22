"""
관리자 계정 admin / 1234 (이미 있으면 비밀번호만 재설정).

  python manage.py bootstrap_admin
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from users.models import UserProfile

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "1234"


class Command(BaseCommand):
    help = f"슈퍼유저 {DEFAULT_USERNAME!r} 생성 또는 비밀번호 재설정"

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=DEFAULT_USERNAME,
            defaults={
                "email": "admin@localhost",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        if not created:
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.save(update_fields=["is_staff", "is_superuser", "is_active"])
        user.set_password(DEFAULT_PASSWORD)
        user.save(update_fields=["password"])
        UserProfile.objects.get_or_create(user=user)
        self.stdout.write(
            self.style.SUCCESS(
                f"OK: username={DEFAULT_USERNAME!r} password={DEFAULT_PASSWORD!r}"
            )
        )
