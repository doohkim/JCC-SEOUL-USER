"""카카오 아바타 히스토리 보존 · 사용자 업로드만 표시."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.templatetags.static import static

from users.mixins import ensure_user_profile
from users.models import UserProfile
from users.services.kakao_auth import create_or_update_kakao_user
from users.services.user_avatar import user_profile_avatar_api_value, user_profile_avatar_url

User = get_user_model()


class _KakaoBackendStub:
    name = "kakao"


class KakaoAvatarDisplayTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="kakao_12345", password="x")
        ensure_user_profile(cls.user)

    def _fake_image_bytes(self) -> bytes:
        return b"\xff\xd8\xff\xe0" + b"\x00" * 100

    @patch("users.services.kakao_auth._download_image_bytes")
    def test_kakao_saves_history_not_profile_avatar(self, mock_download):
        mock_download.return_value = (self._fake_image_bytes(), ".jpg")
        image_url = "https://k.kakaocdn.net/example/profile.jpg"
        create_or_update_kakao_user(
            strategy=None,
            backend=_KakaoBackendStub(),
            uid="12345",
            details={"nickname": "카카오유저"},
            user=self.user,
            response={
                "kakao_account": {
                    "profile": {
                        "nickname": "카카오유저",
                        "profile_image_url": image_url,
                    }
                }
            },
        )
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.avatar_history.count(), 1)
        self.assertFalse(profile.avatar_user_uploaded)
        self.assertFalse(bool(profile.avatar))

    def test_kakao_avatar_in_db_not_shown_without_user_upload_flag(self):
        profile = UserProfile.objects.get(user=self.user)
        profile.avatar.save(
            "kakao_legacy.jpg",
            SimpleUploadedFile("kakao_legacy.jpg", self._fake_image_bytes(), "image/jpeg"),
            save=False,
        )
        profile.avatar_user_uploaded = False
        profile.save(update_fields=["avatar", "avatar_user_uploaded", "updated_at"])

        self.assertEqual(user_profile_avatar_url(self.user), static("attendance/default-avatar.svg"))
        self.assertEqual(user_profile_avatar_api_value(self.user), "")

    def test_user_uploaded_avatar_shown(self):
        profile = UserProfile.objects.get(user=self.user)
        profile.avatar.save(
            "my_upload.jpg",
            SimpleUploadedFile("my_upload.jpg", self._fake_image_bytes(), "image/jpeg"),
            save=False,
        )
        profile.avatar_user_uploaded = True
        profile.save(update_fields=["avatar", "avatar_user_uploaded", "updated_at"])
        self.user = User.objects.get(pk=self.user.pk)

        url = user_profile_avatar_url(self.user)
        self.assertIn("my_upload", url)
        self.assertEqual(user_profile_avatar_api_value(self.user), url)

    def _valid_jpeg_upload(self, name: str = "avatar.jpg") -> SimpleUploadedFile:
        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (8, 8), color=(120, 140, 160)).save(buf, format="JPEG")
        return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")

    def test_profile_post_sets_user_uploaded_flag(self):
        from django.test import Client
        from django.urls import reverse

        client = Client()
        client.force_login(self.user)
        r = client.post(
            reverse("user_profile"),
            {
                "real_name": "홍길동",
                "display_name": "",
                "phone": "010-1234-5678",
                "bio": "",
                "avatar": self._valid_jpeg_upload(),
            },
        )
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["form"].errors)
        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.avatar_user_uploaded)
        self.assertTrue(bool(profile.avatar.name))
