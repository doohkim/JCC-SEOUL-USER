"""공지 이미지 일괄 재압축 커맨드 테스트."""

from __future__ import annotations

import io
import shutil
import tempfile

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image

from notices.models import Notice


def _large_jpeg_bytes(width: int = 2400, height: int = 1600) -> bytes:
    buf = io.BytesIO()
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for x in range(0, width, 8):
        for y in range(0, height, 8):
            pixels[x, y] = (x % 255, y % 255, (x + y) % 255)
    image.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


class RecompressNoticeImagesCommandTests(TestCase):
    def setUp(self):
        self._media_dir = tempfile.mkdtemp()
        self._settings = override_settings(MEDIA_ROOT=self._media_dir)
        self._settings.enable()

    def tearDown(self):
        self._settings.disable()
        shutil.rmtree(self._media_dir, ignore_errors=True)

    def test_dry_run_reports_thumbnail_savings(self):
        notice = Notice.objects.create(
            title="대용량",
            body="<p>본문</p>",
            scope=Notice.Scope.ALL,
        )
        notice.thumbnail.save(
            "big.jpg", ContentFile(_large_jpeg_bytes(4000, 3000)), save=True
        )
        self.assertGreater(notice.thumbnail.size, 200 * 1024)

        out = io.StringIO()
        call_command("recompress_notice_images", "--dry-run", stdout=out)
        self.assertIn("thumbnail", out.getvalue())

        notice.refresh_from_db()
        self.assertGreater(notice.thumbnail.size, 200 * 1024)

    def test_recompress_updates_inline_body_urls(self):
        path = default_storage.save(
            "notices/inline/bodyimg.png",
            ContentFile(_large_jpeg_bytes()),
        )
        old_url = default_storage.url(path)
        Notice.objects.create(
            title="본문 이미지",
            body=f'<p><img src="{old_url}" alt=""></p>',
            scope=Notice.Scope.ALL,
        )

        call_command("recompress_notice_images", "--inline-only", "--min-kb", "50")

        notice = Notice.objects.get(title="본문 이미지")
        self.assertNotIn("bodyimg.png", notice.body)
        self.assertIn("bodyimg.jpg", notice.body)
