"""설정 기반 로그인 백엔드.

``settings.DEFAULT_USERS`` 에 정의된 운영/개발 계정을 로그인 시점에 검증한다.
DB 에 계정이 없으면 즉시 생성하고, 비밀번호 해시는 설정값으로 동기화한다.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password

User = get_user_model()

__all__ = ("SettingsBackend",)

# DEFAULT_USERS 항목 중 User 모델 필드가 아닌 키 (생성 시 제외).
_NON_FIELD_KEYS = {"name", "password"}


class SettingsBackend:
    """``DEFAULT_USERS`` 시드 계정용 인증 백엔드.

    - username 이 ``DEFAULT_USERS`` 에 있고 비밀번호가 맞으면 통과.
    - 계정이 없으면 생성, 있으면 권한/비밀번호 해시를 설정값으로 동기화.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username:
            return None

        user_dict = settings.DEFAULT_USERS.get(username)
        if not user_dict:
            return None

        stored_password = user_dict.get("password")
        if not stored_password or not check_password(password, stored_password):
            return None

        defaults = {
            key: value
            for key, value in user_dict.items()
            if key not in _NON_FIELD_KEYS
        }

        user, created = User.objects.get_or_create(
            username=username,
            defaults={**defaults, "password": stored_password},
        )

        # 기존 계정이면 권한/비밀번호 해시를 설정값과 동기화한다.
        changed = False
        for key, value in defaults.items():
            if getattr(user, key, None) != value:
                setattr(user, key, value)
                changed = True
        if user.password != stored_password:
            user.password = stored_password
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if changed and not created:
            user.save()

        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
