"""drf-spectacular — 연동 서비스 키 인증을 OpenAPI 보안 스키마에 노출."""

from __future__ import annotations

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class IntegrationServiceAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = "users.authentication.IntegrationServiceAuthentication"
    name = "IntegrationServiceKey"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "X-JCC-Integration-Key",
            "description": "또는 `Authorization: Integration <키>`",
        }
