from ._base import *

DEBUG = False

AWS_LOCATION = "production"

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
WSGI_APPLICATION = "config.wsgi.production.application"

# Sentry
# sentry_init(ENV)

# Database
DB_TARGET = os.environ.get("DB_TARGET")
if DB_TARGET == "onprem":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": secrets.DB_HOST_PRODUCTION,
            "PORT": secrets.DB_PORT_PRODUCTION,
            "NAME": secrets.DB_NAME_PRODUCTION,
            "USER": secrets.DB_USERNAME_PRODUCTION,
            "PASSWORD": secrets.DB_PASSWORD_PRODUCTION,
        },
    }
elif DB_TARGET == "rds":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": secrets.RDS_HOST_PRODUCTION,
            "PORT": secrets.RDS_PORT_PRODUCTION,
            "NAME": secrets.RDS_NAME_PRODUCTION,
            "USER": secrets.RDS_USERNAME_PRODUCTION,
            "PASSWORD": secrets.RDS_PASSWORD_PRODUCTION,
        },
    }
else:
    print("Invalid DB_TARGET")

SOCIAL_AUTH_KAKAO_REDIRECT_URI = 'https://shalom.jcc-seoul.com/auth/complete/kakao/'

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
