from ._base import *

DEBUG = False

AWS_STORAGE_BUCKET_NAME = (
    os.environ.get("AWS_STORAGE_BUCKET_NAME_DEV")
    or os.environ.get("AWS_STORAGE_BUCKET_NAME")
    or ""
).strip()
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "ap-northeast-2").strip()
AWS_S3_CUSTOM_DOMAIN = os.environ.get("AWS_S3_CUSTOM_DOMAIN", "").strip() or None
AWS_LOCATION = (
    os.environ.get("AWS_LOCATION_DEV")
    or os.environ.get("AWS_LOCATION")
    or "dev"
).strip("/")

STORAGES, _media_url = build_storage_settings(
    bucket_name=AWS_STORAGE_BUCKET_NAME,
    region_name=AWS_S3_REGION_NAME,
    location=AWS_LOCATION,
    custom_domain=AWS_S3_CUSTOM_DOMAIN,
    access_key=os.environ.get("AWS_ACCESS_KEY_ID", ""),
    secret_key=os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
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
        "HOST": "postgres-django",
        "PORT": 5432,
        "NAME": "jccseoul",
        "USER": "jccseoul",
        "PASSWORD": "jccseoul1!",
    },
}

CSRF_COOKIE_DOMAIN = ".jcc-seoul.com"
CSRF_TRUSTED_ORIGINS = [
    f"https://*.dev.jcc-seoul.com",
    f"https://shalom.dev.jcc-seoul.com",
    f"https://shalom.admin.dev.jcc-seoul.com",
    f"https://shalom.api.dev.jcc-seoul.com",
    f"https://shalom.docs.dev.jcc-seoul.com",
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
    "shalom.admin.dev.jcc-seoul.com",
    "shalom.api.dev.jcc-seoul.com",
    "shalom.docs.dev.jcc-seoul.com",
    "*.dev.jcc-seoul.com",
]
# Subdomain
# SUBDOMAIN_DOMAIN = "localhost" if IS_LOCAL else "shalom.dev.jcc-seoul.com"
