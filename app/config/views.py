"""소규모 뷰 헬퍼 (URL 라우팅 전용)."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpResponseRedirect


def api_root_redirect(request):
    """
    기본 호스트는 로그인으로, docs 호스트는 Swagger UI로 보냄.
    """
    host = request.get_host().split(":")[0].lower()
    if host in getattr(settings, "DOCS_SWAGGER_HOSTS", frozenset()):
        return HttpResponseRedirect("/api/schema/swagger-ui/")
    return HttpResponseRedirect("/login/?next=/attendance/")
