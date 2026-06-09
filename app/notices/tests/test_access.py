"""공지·타임테이블 접근 권한 테스트."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from users.models import Division, Region, UserProfile

User = get_user_model()


class _NoticeAccessFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="notice_test_div", name="공지테스트부"
        )
        cls.superuser = User.objects.create_superuser(
            username="notice_super", password="x"
        )
        cls.pending_user = User.objects.create_user(
            username="notice_pending", password="x"
        )
        cls.pending_profile = UserProfile.objects.create(
            user=cls.pending_user,
            onboarding_status=UserProfile.OnboardingStatus.PENDING,
            requested_division=cls.div,
        )
        cls.approved_user = User.objects.create_user(
            username="notice_approved", password="x"
        )
        cls.approved_profile = UserProfile.objects.create(
            user=cls.approved_user,
            onboarding_status=UserProfile.OnboardingStatus.APPROVED,
            requested_division=cls.div,
        )
        cls.rejected_user = User.objects.create_user(
            username="notice_rejected", password="x"
        )
        cls.rejected_profile = UserProfile.objects.create(
            user=cls.rejected_user,
            onboarding_status=UserProfile.OnboardingStatus.REJECTED,
            requested_division=cls.div,
        )
        cls.unsubmitted_user = User.objects.create_user(
            username="notice_unsubmitted", password="x"
        )
        UserProfile.objects.create(
            user=cls.unsubmitted_user,
            onboarding_status=UserProfile.OnboardingStatus.PENDING,
        )

    def setUp(self):
        self.client = Client()


class NoticeAccessTests(_NoticeAccessFixture):
    def test_anonymous_redirects_to_login(self):
        r = self.client.get(reverse("notice_list"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r.url)

    def test_pending_with_application_can_list(self):
        self.client.force_login(self.pending_user)
        r = self.client.get(reverse("notice_list"))
        self.assertEqual(r.status_code, 200)

    def test_approved_can_list(self):
        self.client.force_login(self.approved_user)
        r = self.client.get(reverse("notice_list"))
        self.assertEqual(r.status_code, 200)

    def test_rejected_redirects_to_onboarding(self):
        self.client.force_login(self.rejected_user)
        r = self.client.get(reverse("notice_list"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/onboarding/", r.url)

    def test_unsubmitted_pending_redirects_to_onboarding(self):
        self.client.force_login(self.unsubmitted_user)
        r = self.client.get(reverse("notice_list"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/onboarding/", r.url)

    def test_timetable_same_rules(self):
        self.client.force_login(self.pending_user)
        self.assertEqual(self.client.get(reverse("timetable")).status_code, 200)
        self.client.force_login(self.rejected_user)
        r = self.client.get(reverse("timetable"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/onboarding/", r.url)


class NoticeWriteAccessTests(_NoticeAccessFixture):
    def test_superuser_can_open_create_form(self):
        self.client.force_login(self.superuser)
        r = self.client.get(reverse("notice_create"))
        self.assertEqual(r.status_code, 200)

    def test_superuser_can_create_notice(self):
        self.client.force_login(self.superuser)
        r = self.client.post(
            reverse("notice_create"),
            {"title": "테스트 공지", "body": "내용", "is_pinned": False},
        )
        self.assertEqual(r.status_code, 302)
        from notices.models import Notice

        self.assertTrue(Notice.objects.filter(title="테스트 공지").exists())

    def test_pending_user_cannot_create(self):
        self.client.force_login(self.pending_user)
        r = self.client.get(reverse("notice_create"))
        self.assertEqual(r.status_code, 403)

    def test_approved_user_cannot_create(self):
        self.client.force_login(self.approved_user)
        r = self.client.get(reverse("notice_create"))
        self.assertEqual(r.status_code, 403)
