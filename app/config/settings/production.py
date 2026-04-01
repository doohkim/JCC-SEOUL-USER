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
        "HOST": "localhost",
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

ALLOWED_HOSTS += [
    # jcc-seoul.com
    "localhost",
    "shalom.admin.jcc-seoul.com",
    "shalom.api.jcc-seoul.com",
    "shalom.docs.jcc-seoul.com",
    "*.jcc-seoul.com",
]
# Subdomain
# SUBDOMAIN_DOMAIN = "localhost" if IS_LOCAL else "shalom.jcc-seoul.com"
