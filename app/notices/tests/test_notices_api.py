"""함께하기(공지) REST API."""

from __future__ import annotations

from django.test import TestCase
from rest_framework.authtoken.models import Token

from notices.models import Notice
from users.models import User, UserProfile


class NoticeListAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username="notice_staff",
            password="x",
            is_staff=True,
        )
        cls.pending = User.objects.create_user(username="pending_user", password="x")
        pending_profile = UserProfile.objects.create(
            user=cls.pending,
            onboarding_status=UserProfile.OnboardingStatus.PENDING,
        )
        pending_profile.requested_division_id = None

        cls.notice = Notice.objects.create(
            title="함께하기 첫 공지",
            body="<p>본문</p>",
            is_pinned=True,
            created_by=cls.staff,
        )

    def setUp(self):
        self.client = self.client_class()

    def _auth(self, user: User):
        token, _ = Token.objects.get_or_create(user=user)
        return {"HTTP_AUTHORIZATION": f"Token {token.key}"}

    def test_list_requires_auth(self):
        r = self.client.get("/api/v1/notices/")
        self.assertEqual(r.status_code, 403)

    def test_staff_can_list_notices(self):
        r = self.client.get("/api/v1/notices/", **self._auth(self.staff))
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["title"], "함께하기 첫 공지")
        self.assertTrue(body["results"][0]["is_pinned"])

    def test_pending_without_signup_is_forbidden(self):
        r = self.client.get("/api/v1/notices/", **self._auth(self.pending))
        self.assertEqual(r.status_code, 403)

    def test_detail_increments_view_count(self):
        before = self.notice.view_count
        r = self.client.get(
            f"/api/v1/notices/{self.notice.pk}/",
            **self._auth(self.staff),
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["title"], "함께하기 첫 공지")
        self.assertIn("body", body)
        self.assertEqual(body["view_count"], before + 1)
