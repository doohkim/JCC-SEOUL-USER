"""Host-based routing guard for subdomain split deployment."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpResponseRedirect


class SubdomainRoutingMiddleware:
    """
    Enforce host-to-path boundaries when subdomain routing is enabled.

    - admin host: only Django admin paths
    - api host: only API/auth paths
    - docs host: docs page only
    - app host: regular UI paths (plus auth callback)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "SUBDOMAIN_ROUTING_ENABLED", False):
            return self.get_response(request)

        host = request.get_host().split(":")[0].lower()
        path = request.path

        app_host = (getattr(settings, "APP_HOST", "") or "").lower()
        admin_host = (getattr(settings, "ADMIN_HOST", "") or "").lower()
        api_host = (getattr(settings, "API_HOST", "") or "").lower()
        docs_host = (getattr(settings, "DOCS_HOST", "") or "").lower()

        is_admin_path = path.startswith("/django-admin/") or path.startswith("/admin/")
        is_api_path = path.startswith("/api/")
        is_auth_path = path.startswith("/auth/")
        is_docs_path = path.startswith("/docs/")

        if host == admin_host:
            if path == "/":
                return HttpResponseRedirect("/django-admin/")
            if not is_admin_path:
                return HttpResponseRedirect("/django-admin/")

        if host == api_host:
            if path == "/":
                return HttpResponseRedirect("/api/v1/attendance/")
            if not (is_api_path or is_auth_path):
                return HttpResponseRedirect("/api/v1/attendance/")

        if host == docs_host:
            if path == "/":
                return HttpResponseRedirect("/docs/")
            if not is_docs_path:
                return HttpResponseRedirect("/docs/")

        if host == app_host:
            if is_admin_path:
                return HttpResponseRedirect("/")

        return self.get_response(request)
