import sys

from . import _secrets as secrets
from ._c import *
from ._path import *
from .auth import *
from .baker import *
from .cache import *
from .celery import *
from .databases import *
from .drf import *
from .installed_apps import *
from .middleware import *
from .password import *
from .phonenumber import *
from .static import *
from .logging import *
from .subdomain import *
from .attendance import *
from .templates import *

IS_RUNSERVER = len(sys.argv) > 1 and sys.argv[1] == "runserver"
IS_LOCAL = IS_RUNSERVER or os.environ.get("IS_LOCAL") == "1"
IS_DOCKER = bool(os.environ.get("DOCKER"))
ENV = os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings.local").rsplit(".", 1)[-1]
ENV_IS_PRODUCTION = ENV in ["production", "celery.py", "staff"]
DEBUG = IS_LOCAL or False  # static url활성화를 위해 로컬이면 DEBUG = True

ATOMIC_REQUESTS = True
ALLOWED_HOSTS = ["health-check"]
SECRET_KEY = "django-insecure-$6gta((^uu4h+#9*^&buib(uwgsjxyepvve3o^sp7vlf8jav#x"

if DEBUG:
    ALLOWED_HOSTS += [
        "admin.localhost",
        "api.localhost",
        "docs.localhost",
        "*",
    ]

ROOT_URLCONF = "config.urls.api"

WSGI_APPLICATION = "config.wsgi.local.application"

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_L10N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# django-cors-headers
CORS_ALLOW_ALL_ORIGINS = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True