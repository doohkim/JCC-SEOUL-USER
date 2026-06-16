"""공지 본문 TinyMCE HTML 살균(nh3) 테스트."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from notices.forms import NoticeForm
from notices.models import Notice
from users.models import Division, Region, UserProfile

User = get_user_model()


class NoticeFormSanitizeTests(TestCase):
    def test_clean_body_strips_script(self):
        form = NoticeForm(
            data={
                "title": "살균",
                "body": '<p>본문</p><script>alert("xss")</script>',
                "scope": "all",
                "is_pinned": False,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("script", form.cleaned_data["body"].lower())
        self.assertIn("본문", form.cleaned_data["body"])

    def test_clean_body_preserves_allowed_markup(self):
        raw = "<p><strong>굵게</strong></p><ul><li>항목</li></ul>"
        form = NoticeForm(
            data={
                "title": "서식",
                "body": raw,
                "scope": "all",
                "is_pinned": False,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        cleaned = form.cleaned_data["body"]
        self.assertIn("<strong>굵게</strong>", cleaned)
        self.assertIn("<ul>", cleaned)
        self.assertIn("<li>항목</li>", cleaned)


class NoticeCreateSanitizeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="sanitize_div", name="살균테스트부"
        )
        cls.superuser = User.objects.create_superuser(
            username="sanitize_super", password="x"
        )
        UserProfile.objects.create(
            user=cls.superuser,
            onboarding_status=UserProfile.OnboardingStatus.APPROVED,
            requested_division=cls.div,
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.superuser)

    def test_create_post_strips_script_from_body(self):
        body = '<p>저장</p><script>alert(1)</script><strong>강조</strong>'
        r = self.client.post(
            reverse("notice_create"),
            {
                "title": "살균 저장 테스트",
                "body": body,
                "is_pinned": False,
                "scope": "all",
            },
        )
        self.assertEqual(r.status_code, 302)
        notice = Notice.objects.get(title="살균 저장 테스트")
        self.assertNotIn("script", notice.body.lower())
        self.assertIn("<strong>강조</strong>", notice.body)

    def test_form_page_includes_tinymce_media(self):
        r = self.client.get(reverse("notice_create"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "tinymce")
        self.assertContains(r, "jcc-notice-imageUploader")
