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
    f"http://*.jcc-seoul.com",
    f"https://*.jcc-seoul.com",
    f"http://shalom.jcc-seoul.com",
    f"https://shalom.jcc-seoul.com",
    f"http://shalom.admin.jcc-seoul.com",
    f"https://shalom.admin.jcc-seoul.com",
    f"http://shalom.api.jcc-seoul.com",
    f"https://shalom.api.jcc-seoul.com",
    f"http://shalom.docs.jcc-seoul.com",
    f"https://shalom.docs.jcc-seoul.com",
]
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

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
