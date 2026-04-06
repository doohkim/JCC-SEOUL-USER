"""연동(Integration) API — 서비스 키·토큰 검증."""

import json

import yaml
from django.test import TestCase, override_settings
from django.test.client import Client
from rest_framework.authtoken.models import Token

from users.models import ExternalServiceClient, User
from users.models.external_service import generate_integration_key_pair


class IntegrationAPITests(TestCase):
    """``X-JCC-Integration-Key`` 로 보호되는 ``/api/v1/integration/`` 엔드포인트."""

    @classmethod
    def setUpTestData(cls):
        raw, prefix, key_hash = generate_integration_key_pair()
        cls.integration_key = raw
        ExternalServiceClient.objects.create(
            name="pytest-integration",
            label="pytest",
            key_prefix=prefix,
            key_hash=key_hash,
        )
        cls.user = User.objects.create_user(username="int_api_user", password="unused-here")
        cls.token = Token.objects.create(user=cls.user)

    def setUp(self):
        self.client = Client()

    def _headers(self):
        return {"HTTP_X_JCC_INTEGRATION_KEY": self.integration_key}

    def test_ping_without_key_returns_401(self):
        r = self.client.get("/api/v1/integration/ping/")
        self.assertEqual(r.status_code, 401)

    def test_ping_with_invalid_key_returns_401(self):
        # prefix는 맞고 해시만 틀리게 해서 AuthenticationFailed(401)를 확실히 검증
        r = self.client.get(
            "/api/v1/integration/ping/",
            HTTP_X_JCC_INTEGRATION_KEY=self.integration_key + "-tampered",
        )
        self.assertEqual(r.status_code, 401)

    def test_ping_with_valid_key_returns_200(self):
        r = self.client.get("/api/v1/integration/ping/", **self._headers())
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("client"), "pytest-integration")

    def test_verify_token_without_integration_key_returns_401(self):
        r = self.client.post(
            "/api/v1/integration/verify-token/",
            data={"token": self.token.key},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 401)

    def test_verify_token_valid_returns_user_body(self):
        r = self.client.post(
            "/api/v1/integration/verify-token/",
            data={"token": self.token.key},
            content_type="application/json",
            **self._headers(),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body.get("valid"))
        self.assertIn("user", body)
        self.assertEqual(body["user"].get("username"), "int_api_user")

    def test_user_detail_without_key_returns_401(self):
        r = self.client.get(f"/api/v1/integration/users/{self.user.pk}/")
        self.assertEqual(r.status_code, 401)

    def test_user_detail_with_key(self):
        r = self.client.get(
            f"/api/v1/integration/users/{self.user.pk}/",
            **self._headers(),
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["user"]["username"], "int_api_user")

    def test_permissions_check_empty_checks(self):
        r = self.client.post(
            "/api/v1/integration/permissions/check/",
            data={"user_id": self.user.pk},
            content_type="application/json",
            **self._headers(),
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.json())

    @override_settings(ALLOW_INTEGRATION_DEBUG_TOKEN=True)
    def test_debug_issue_token_when_allowed(self):
        r = self.client.post(
            "/api/v1/integration/debug/issue-token/",
            data={"user_id": self.user.pk},
            content_type="application/json",
            **self._headers(),
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("token", r.json())

    @override_settings(ALLOW_INTEGRATION_DEBUG_TOKEN=False)
    def test_debug_issue_token_disabled(self):
        r = self.client.post(
            "/api/v1/integration/debug/issue-token/",
            data={"user_id": self.user.pk},
            content_type="application/json",
            **self._headers(),
        )
        self.assertEqual(r.status_code, 404)


class OpenAPISchemaTests(TestCase):
    """drf-spectacular 스키마·Swagger UI 경로."""

    def test_schema_openapi_200(self):
        c = Client()
        r = c.get("/api/schema/")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        if r.headers.get("Content-Type", "").startswith("application/json"):
            data = json.loads(body)
        else:
            data = yaml.safe_load(body)
        self.assertIn("openapi", data)

    def test_schema_tags_grouped_by_django_app(self):
        c = Client()
        r = c.get("/api/schema/")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        if r.headers.get("Content-Type", "").startswith("application/json"):
            data = json.loads(body)
        else:
            data = yaml.safe_load(body)
        paths = data.get("paths") or {}
        self.assertEqual(
            paths["/api/v1/integration/ping/"]["get"]["tags"],
            ["users"],
        )
        self.assertEqual(
            paths["/api/v1/attendance/divisions/"]["get"]["tags"],
            ["attendance"],
        )
        self.assertEqual(
            paths["/api/v1/member/"]["get"]["tags"],
            ["registry"],
        )
        self.assertEqual(
            paths["/api/v1/counseling/counselors/"]["get"]["tags"],
            ["counseling"],
        )

    def test_swagger_ui_200(self):
        c = Client()
        r = c.get("/api/schema/swagger-ui/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "swagger-ui", status_code=200)

    def test_docs_host_root_redirects_to_swagger(self):
        c = Client()
        r = c.get("/", HTTP_HOST="docs.localhost")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "/api/schema/swagger-ui/")
