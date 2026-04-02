from ._base import *

DEBUG = False

# ENV settings
WSGI_APPLICATION = "config.wsgi.production.application"

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
