SUBDOMAIN_DOMAIN = "jcc-seoul.com"

SUBDOMAIN_DEFAULT = "shalom"
SUBDOMAIN_ADMIN = "shalom.admin"
SUBDOMAIN_API = "shalom.api"


SUBDOMAIN_URLCONFS = {
    SUBDOMAIN_DEFAULT: "config.urls.api",
    SUBDOMAIN_ADMIN: "config.urls.admin",
    SUBDOMAIN_API: "config.urls.api",
}

# ``/`` 접근 시 Swagger UI로 보낼 호스트 (예: docs 서브도메인).
DOCS_SWAGGER_HOSTS = frozenset(
    {
        "shalom.docs.jcc-seoul.com",
        "docs.localhost",
    }
)
SUBDOMAIN_IGNORE_HOSTS = ["health-check"]
