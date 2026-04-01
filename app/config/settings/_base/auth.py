import os

AUTH_USER_MODEL = "users.User"
AUTHENTICATION_BACKENDS = (
    "social_core.backends.kakao.KakaoOAuth2",
    "django.contrib.auth.backends.ModelBackend",
)

DEFAULT_USERS = {
    "shalom": {
        "name": "shalom",
        "email": "shalom@jcc-seoul.com",
        "password": "pbkdf2_sha256$870000$c1sY6NRPFH9lAzRShaKZT8$EbZma8hS8ZhOaljlTib2X/YofKitFOYrO3zn/GcWQjQ=",
        "is_staff": True,
        "is_superuser": True,
    },
}

SOCIAL_AUTH_KAKAO_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
SOCIAL_AUTH_KAKAO_SECRET = os.environ.get("KAKAO_CLIENT_SECRET", "")
SOCIAL_AUTH_KAKAO_REDIRECT_URI = os.environ.get("KAKAO_REDIRECT_URI", "")
SOCIAL_AUTH_KAKAO_SCOPE = ["profile_nickname"]

SOCIAL_AUTH_PIPELINE = (
    "social_core.pipeline.social_auth.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.auth_allowed",
    "social_core.pipeline.social_auth.social_user",
    "users.services.kakao_auth.create_or_update_kakao_user",
    "social_core.pipeline.user.get_username",
    "social_core.pipeline.social_auth.associate_by_email",
    "social_core.pipeline.user.create_user",
    "social_core.pipeline.social_auth.associate_user",
    "social_core.pipeline.social_auth.load_extra_data",
    "social_core.pipeline.user.user_details",
)

SOCIAL_AUTH_LOGIN_ERROR_URL = "/login/?error=1"
SOCIAL_AUTH_LOGIN_REDIRECT_URL = "/attendance/?welcome=1"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/attendance/?welcome=1"
LOGOUT_REDIRECT_URL = "/login/"
