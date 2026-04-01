from ._base import *

DEBUG = True
WSGI_APPLICATION = "config.wsgi.local.application"

# Subdomain
SUBDOMAIN_DOMAIN = "localhost"
SUBDOMAIN_ADMIN = "admin"
SUBDOMAIN_API = "api"
SUBDOMAIN_DEFAULT = None

SUBDOMAIN_URLCONFS = {
    SUBDOMAIN_DEFAULT: "config.urls.api",
    SUBDOMAIN_ADMIN: "config.urls.admin",
    SUBDOMAIN_API: "config.urls.api",
}

# Notebook
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

# django-debug-toolbar
INSTALLED_APPS += [
    "debug_toolbar",
]
INTERNAL_IPS = [
    "*",
    "127.0.0.1",
]
MIDDLEWARE.append("debug_toolbar.middleware.DebugToolbarMiddleware")


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


CSRF_TRUSTED_ORIGINS = [
    "https://*.jcc-seoul.com",
    "https://localhost:8000",
]
ALLOWED_HOSTS += [
    "admin.localhost",
    "api.localhost",
    "docs.localhost",
    "tests.localhost",
    "*",
]
ALLOWED_HOSTS += [f"192.168.0.{value}" for value in range(1, 256)]
# ALLOWED_HOSTS = ["localhost", "127.0.0.1", "api.localhost"]
