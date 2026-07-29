from ._base import *

DEBUG = False

AWS_LOCATION = "dev"

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

# 개발 배포 도메인은 ``jcc-seoul.com`` 앞에 ``shalom.dev.*`` 구조를 사용한다.
# 공통 설정의 운영용 키(``shalom.admin`` 등)를 그대로 두면 관리자 호스트도
# 기본 사용자 URLconf로 처리되어 /login/이 카카오 로그인으로 연결된다.
SUBDOMAIN_DEFAULT = "shalom.dev"
SUBDOMAIN_ADMIN = "shalom.dev.admin"
SUBDOMAIN_API = "shalom.dev.api"
SUBDOMAIN_DOCS = "shalom.dev.docs"

SUBDOMAIN_URLCONFS = {
    SUBDOMAIN_DEFAULT: "config.urls.api",
    SUBDOMAIN_ADMIN: "config.urls.admin",
    SUBDOMAIN_API: "config.urls.api",
    SUBDOMAIN_DOCS: "config.urls.api",
}

# ENV settings
WSGI_APPLICATION = "config.wsgi.dev.application"

# Sentry
# sentry_init(ENV)

# Database
# Docker 네트워크 안에서는 postgres 컨테이너 포트(5432)를 쓴다.
# secrets.DB_PORT_DEV(55432)는 호스트 포트 매핑용이라 컨테이너→컨테이너 접속에 쓰면 Connection refused.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": secrets.DB_HOST_DEV,
        "PORT": 5432,
        "NAME": secrets.DB_NAME_DEV,
        "USER": secrets.DB_USERNAME_DEV,
        "PASSWORD": secrets.DB_PASSWORD_DEV,
    },
}
SOCIAL_AUTH_KAKAO_REDIRECT_URI = (
    "https://shalom.dev.jcc-seoul.com:8443/auth/complete/kakao/"
)

CSRF_COOKIE_DOMAIN = ".jcc-seoul.com"
CSRF_TRUSTED_ORIGINS = [
    f"https://*.dev.jcc-seoul.com",
    f"https://shalom.dev.jcc-seoul.com",
    f"https://shalom.dev.admin.jcc-seoul.com",
    f"https://shalom.dev.api.jcc-seoul.com",
    f"https://shalom.dev.docs.jcc-seoul.com",
    f"https://shalom.dev.*.jcc-seoul.com",
    # 공유기 포트포워딩(외부 8443 → 내부 443)으로 접속할 때
    f"https://shalom.dev.jcc-seoul.com:8443",
    f"https://shalom.dev.admin.jcc-seoul.com:8443",
    f"https://shalom.dev.api.jcc-seoul.com:8443",
    f"https://shalom.dev.docs.jcc-seoul.com:8443",
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
    "shalom.dev.admin.jcc-seoul.com",
    "shalom.dev.api.jcc-seoul.com",
    "shalom.dev.docs.jcc-seoul.com",
    "shalom.dev.*.jcc-seoul.com",
]
# Subdomain
# SUBDOMAIN_DOMAIN = "localhost" if IS_LOCAL else "shalom.dev.jcc-seoul.com"
