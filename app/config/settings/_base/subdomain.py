SUBDOMAIN_DOMAIN = "jcc-seoul.com"

SUBDOMAIN_DEFAULT = "shalom"
SUBDOMAIN_ADMIN = "shalom.admin"
SUBDOMAIN_API = "shalom.api"


SUBDOMAIN_URLCONFS = {
    SUBDOMAIN_DEFAULT: "config.urls.api",
    SUBDOMAIN_ADMIN: "config.urls.admin",
    SUBDOMAIN_API: "config.urls.api",
}
SUBDOMAIN_IGNORE_HOSTS = ["health-check"]
