from ._base import *

DEBUG = False

AWS_LOCATION = "dev"

STORAGES, _media_url = build_storage_settings(
    bucket_name=AWS_STORAGE_BUCKET_NAME,
    region_name=AWS_S3_REGION_NAME,
    location=AWS_LOCATION,
    custom_domain=AWS_S3_CUSTOM_DOMAIN,
    access_key=AWS_ACCESS_KEY_ID,
    secret_key=AWS_SECRET_ACCESS_KEY,
)
if _media_url:
    MEDIA_URL = _media_url

# ENV settings
WSGI_APPLICATION = "config.wsgi.dev.application"

# Sentry
# sentry_init(ENV)

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": secrets.DB_HOST_DEV,
        "PORT": secrets.DB_PORT_DEV,
        "NAME": secrets.DB_NAME_DEV,
        "USER": secrets.DB_USERNAME_DEV,
        "PASSWORD": secrets.DB_PASSWORD_DEV,
    },
}
SOCIAL_AUTH_KAKAO_REDIRECT_URI = "https://shalom.dev.jcc-seoul.com/auth/complete/kakao/"

CSRF_COOKIE_DOMAIN = ".jcc-seoul.com"
CSRF_TRUSTED_ORIGINS = [
    f"https://*.dev.jcc-seoul.com",
    f"https://shalom.dev.jcc-seoul.com",
    f"https://shalom.dev.admin.jcc-seoul.com",
    f"https://shalom.dev.api.jcc-seoul.com",
    f"https://shalom.dev.docs.jcc-seoul.com",
    f"https://shalom.dev.*.jcc-seoul.com",
]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
# nginx가 전달한 X-Forwarded-Proto를 기준으로 HTTPS 요청을 인식한다.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

ALLOWED_HOSTS += [
    # jcc-seoul.com
    "localhost",
    "shalom.dev.jcc-seoul.com",
    "shalom.dev.admin.jcc-seoul.com",
    "shalom.dev.api.jcc-seoul.com",
    "shalom.dev.docs.jcc-seoul.com",
    "shalom.dev.*.jcc-seoul.com",
]
# Subdomain
# SUBDOMAIN_DOMAIN = "localhost" if IS_LOCAL else "shalom.dev.jcc-seoul.com"
