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

AWS_LOCATION = "local"

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

# 원격 RDS/SSH 터널에서는 패널별 추가 SQL 때문에 요청 시간이 크게 늘어난다.
# 필요한 경우에만 ENABLE_DEBUG_TOOLBAR=1로 명시해 켠다.
ENABLE_DEBUG_TOOLBAR = os.environ.get("ENABLE_DEBUG_TOOLBAR", "0") == "1"
if ENABLE_DEBUG_TOOLBAR:
    INSTALLED_APPS += ["debug_toolbar"]
    INTERNAL_IPS = ["*", "127.0.0.1"]
    MIDDLEWARE.append("debug_toolbar.middleware.DebugToolbarMiddleware")


# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.sqlite3",
#         "NAME": BASE_DIR / "db.sqlite3",
#     }
# }

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": secrets.RDS_HOST_PRODUCTION,
        "PORT": 55432,
        "NAME": secrets.RDS_NAME_PRODUCTION,
        "USER": secrets.RDS_USERNAME_PRODUCTION,
        "PASSWORD": secrets.RDS_PASSWORD_PRODUCTION,
    },
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
