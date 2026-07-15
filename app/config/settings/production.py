from ._base import *

DEBUG = False

AWS_STORAGE_BUCKET_NAME = (
    os.environ.get("AWS_STORAGE_BUCKET_NAME_PRODUCTION")
    or os.environ.get("AWS_STORAGE_BUCKET_NAME")
    or ""
).strip()
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "ap-northeast-2").strip()
AWS_S3_CUSTOM_DOMAIN = os.environ.get("AWS_S3_CUSTOM_DOMAIN", "").strip() or None
AWS_LOCATION = (
    os.environ.get("AWS_LOCATION_PRODUCTION")
    or os.environ.get("AWS_LOCATION")
    or "production"
).strip("/")

if AWS_STORAGE_BUCKET_NAME:
    _s3_options = {
        "bucket_name": AWS_STORAGE_BUCKET_NAME,
        "region_name": AWS_S3_REGION_NAME,
        "default_acl": None,
        "querystring_auth": False,
        "file_overwrite": False,
        "location": AWS_LOCATION,
    }
    if os.environ.get("AWS_ACCESS_KEY_ID"):
        _s3_options["access_key"] = os.environ["AWS_ACCESS_KEY_ID"]
    if os.environ.get("AWS_SECRET_ACCESS_KEY"):
        _s3_options["secret_key"] = os.environ["AWS_SECRET_ACCESS_KEY"]
    if AWS_S3_CUSTOM_DOMAIN:
        _s3_options["custom_domain"] = AWS_S3_CUSTOM_DOMAIN

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": _s3_options,
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
        },
    }

    _media_domain = AWS_S3_CUSTOM_DOMAIN or f"{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com"
    MEDIA_URL = f"https://{_media_domain}/{AWS_LOCATION}/"
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
        },
    }

# ENV settings
WSGI_APPLICATION = "config.wsgi.production.application"

# Sentry
# sentry_init(ENV)

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": "jcc-seoul-user-prod.cbi5eibp69vv.ap-northeast-2.rds.amazonaws.com",
        "PORT": 55432,
        "NAME": "jccseoul",
        "USER": "jccseoul",
        "PASSWORD": "jccseoul1!",
    },
}

CSRF_COOKIE_DOMAIN = ".jcc-seoul.com"
CSRF_TRUSTED_ORIGINS = [
    f"https://*.jcc-seoul.com",
    f"https://shalom.jcc-seoul.com",
    f"https://shalom.admin.jcc-seoul.com",
    f"https://shalom.api.jcc-seoul.com",
    f"https://shalom.docs.jcc-seoul.com",
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
    "shalom.jcc-seoul.com",
    "shalom.admin.jcc-seoul.com",
    "shalom.api.jcc-seoul.com",
    "shalom.docs.jcc-seoul.com",
    "*.jcc-seoul.com",
]
# Subdomain
# SUBDOMAIN_DOMAIN = "localhost" if IS_LOCAL else "shalom.jcc-seoul.com"
