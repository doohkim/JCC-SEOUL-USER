"""공지 본문 인라인 이미지 업로드 엔드포인트 테스트."""

from __future__ import annotations

import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from notices.forms import NoticeForm
from users.models import Division, Region, UserProfile

User = get_user_model()


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (200, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


class NoticeImageUploadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seoul = Region.objects.get(code="seoul")
        cls.div = Division.objects.create(
            region=cls.seoul, code="img_div", name="이미지테스트부"
        )
        cls.superuser = User.objects.create_superuser(
            username="img_super", password="x"
        )
        cls.approved_user = User.objects.create_user(
            username="img_member", password="x"
        )
        UserProfile.objects.create(
            user=cls.approved_user,
            onboarding_status=UserProfile.OnboardingStatus.APPROVED,
            requested_division=cls.div,
        )

    def setUp(self):
        self.client = Client()

    def test_manager_can_upload_png(self):
        self.client.force_login(self.superuser)
        upload = SimpleUploadedFile("a.png", _png_bytes(), content_type="image/png")
        r = self.client.post(reverse("notice_image_upload"), {"file": upload})
        self.assertEqual(r.status_code, 200)
        location = r.json()["location"]
        self.assertTrue(location.startswith("/media/notices/inline/"))
        self.assertTrue(location.endswith(".png"))

    def test_anonymous_cannot_upload(self):
        upload = SimpleUploadedFile("a.png", _png_bytes(), content_type="image/png")
        r = self.client.post(reverse("notice_image_upload"), {"file": upload})
        self.assertEqual(r.status_code, 403)

    def test_non_manager_cannot_upload(self):
        self.client.force_login(self.approved_user)
        upload = SimpleUploadedFile("a.png", _png_bytes(), content_type="image/png")
        r = self.client.post(reverse("notice_image_upload"), {"file": upload})
        self.assertEqual(r.status_code, 403)

    def test_non_image_rejected(self):
        self.client.force_login(self.superuser)
        bad = SimpleUploadedFile("a.txt", b"hello", content_type="text/plain")
        r = self.client.post(reverse("notice_image_upload"), {"file": bad})
        self.assertEqual(r.status_code, 400)

    def test_corrupt_image_rejected(self):
        self.client.force_login(self.superuser)
        bad = SimpleUploadedFile("a.png", b"not-a-real-png", content_type="image/png")
        r = self.client.post(reverse("notice_image_upload"), {"file": bad})
        self.assertEqual(r.status_code, 400)

    def test_get_not_allowed(self):
        self.client.force_login(self.superuser)
        r = self.client.get(reverse("notice_image_upload"))
        self.assertEqual(r.status_code, 405)


class NoticeBodyImageSanitizeTests(TestCase):
    def test_clean_body_keeps_img_and_strips_data_uri(self):
        raw = (
            '<p><img src="/media/notices/inline/x.png" alt="첨부"></p>'
            '<p><img src="data:image/png;base64,AAAA" alt="bad"></p>'
        )
        form = NoticeForm(
            data={"title": "이미지", "body": raw, "scope": "all", "is_pinned": False}
        )
        self.assertTrue(form.is_valid(), form.errors)
        cleaned = form.cleaned_data["body"]
        self.assertIn('src="/media/notices/inline/x.png"', cleaned)
        self.assertNotIn("data:image", cleaned)
