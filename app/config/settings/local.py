from pathlib import Path

from dotenv import load_dotenv

# auth 등 _base가 os.environ을 읽기 전에 반드시 로드할 것 (.deploy/local/env 포함)
_app_dir = Path(__file__).resolve().parent.parent.parent
_repo_root = _app_dir.parent
for _p in (_repo_root / ".env", _app_dir / ".env"):
    if _p.is_file():
        load_dotenv(_p, override=False)
_deploy_local = _repo_root / ".deploy" / "local" / "env"
if _deploy_local.is_file():
    load_dotenv(_deploy_local, override=True)

from ._base import *

DEBUG = True
WSGI_APPLICATION = "config.wsgi.local.application"

AWS_STORAGE_BUCKET_NAME = (
    os.environ.get("AWS_STORAGE_BUCKET_NAME_LOCAL")
    or os.environ.get("AWS_STORAGE_BUCKET_NAME")
    or ""
).strip()
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "ap-northeast-2").strip()
AWS_S3_CUSTOM_DOMAIN = os.environ.get("AWS_S3_CUSTOM_DOMAIN", "").strip() or None
AWS_LOCATION = (
    os.environ.get("AWS_LOCATION_LOCAL")
    or os.environ.get("AWS_LOCATION")
    or "local"
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
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "https://kauth.kakao.com",
]
ALLOWED_HOSTS += [
    "admin.localhost",
    "api.localhost",
    "docs.localhost",
    "tests.localhost",
    "localhost",
    "*",
]
CSRF_TRUSTED_ORIGINS += [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "https://kauth.kakao.com",
]
ALLOWED_HOSTS += [f"192.168.0.{value}" for value in range(1, 256)]
# ALLOWED_HOSTS = ["localhost", "127.0.0.1", "api.localhost"]
