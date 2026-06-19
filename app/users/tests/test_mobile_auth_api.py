"""모바일 카카오 로그인 API."""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase
from rest_framework.authtoken.models import Token

from users.models import User, UserProfile


class KakaoMobileLoginAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.existing = User.objects.create_user(
            username="kakao_12345",
            password="unused",
            signup_source=User.SignupSource.KAKAO,
        )
        UserProfile.objects.create(user=cls.existing, display_name="기존유저")

    def setUp(self):
        self.client = self.client_class()

    @patch("users.apis.mobile_auth.login_with_kakao_access_token")
    def test_missing_access_token_returns_400(self, mock_login):
        r = self.client.post("/api/v1/auth/kakao/", data={}, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        mock_login.assert_not_called()

    @patch("users.services.kakao_mobile_auth._fetch_kakao_profile")
    def test_valid_token_issues_drf_token(self, mock_fetch):
        mock_fetch.return_value = {
            "id": 99999,
            "kakao_account": {
                "profile": {"nickname": "모바일유저", "profile_image_url": ""},
            },
            "properties": {"nickname": "모바일유저"},
        }
        r = self.client.post(
            "/api/v1/auth/kakao/",
            data={"access_token": "fake-kakao-token"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("token", body)
        self.assertTrue(body.get("created"))
        self.assertIn("user", body)
        self.assertEqual(body["user"]["username"], "kakao_99999")

    @patch("users.services.kakao_mobile_auth._fetch_kakao_profile")
    def test_existing_user_reuses_token(self, mock_fetch):
        mock_fetch.return_value = {
            "id": 12345,
            "kakao_account": {"profile": {"nickname": "기존유저"}},
            "properties": {},
        }
        r = self.client.post(
            "/api/v1/auth/kakao/",
            data={"access_token": "fake-kakao-token"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body.get("created"))
        token = Token.objects.get(user=self.existing)
        self.assertEqual(body["token"], token.key)

    def test_me_requires_auth(self):
        r = self.client.get("/api/v1/auth/me/")
        self.assertEqual(r.status_code, 403)

    def test_me_returns_user(self):
        user = User.objects.create_user(username="me_user", password="x")
        token = Token.objects.create(user=user)
        r = self.client.get(
            "/api/v1/auth/me/",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["user"]["username"], "me_user")
