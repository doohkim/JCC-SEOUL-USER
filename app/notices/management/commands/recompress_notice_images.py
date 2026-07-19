"""기존 공지 썸네일·인라인 이미지를 일괄 리사이즈/압축한다.

배포 전에 올라간 대용량 원본(수 MB)은 업로드 훅만으로는 줄지 않는다.
프로덕션에서 한 번 실행한다.

  python manage.py recompress_notice_images
  python manage.py recompress_notice_images --dry-run
"""

from __future__ import annotations

import os

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from notices.models import Notice
from notices.services.images import (
    INLINE_MAX_WIDTH,
    THUMBNAIL_MAX_WIDTH,
    compress_image_bytes,
)


class Command(BaseCommand):
    help = "공지 썸네일·인라인 이미지를 일괄 리사이즈/압축한다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제 저장 없이 대상·절감량만 출력",
        )
        parser.add_argument(
            "--min-kb",
            type=int,
            default=200,
            help="이 크기(KB) 이상 파일만 처리 (기본 200)",
        )
        parser.add_argument(
            "--thumbnails-only",
            action="store_true",
            help="썸네일만 처리",
        )
        parser.add_argument(
            "--inline-only",
            action="store_true",
            help="인라인 이미지만 처리",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        min_bytes = options["min_kb"] * 1024
        do_thumbnails = not options["inline_only"]
        do_inline = not options["thumbnails_only"]

        if dry_run:
            self.stdout.write("DRY RUN — 파일은 변경하지 않습니다.")

        total_saved = 0
        if do_thumbnails:
            total_saved += self._recompress_thumbnails(min_bytes, dry_run)
        if do_inline:
            total_saved += self._recompress_inline(min_bytes, dry_run)

        self.stdout.write(
            self.style.SUCCESS(f"완료: 총 {total_saved / 1024:.1f} KB 절감")
        )

    def _recompress_thumbnails(self, min_bytes: int, dry_run: bool) -> int:
        saved = 0
        qs = Notice.objects.exclude(thumbnail="").only("id", "title", "thumbnail")
        for notice in qs.iterator():
            if not notice.thumbnail:
                continue
            try:
                old_size = notice.thumbnail.size
            except FileNotFoundError:
                self.stdout.write(
                    self.style.WARNING(f"skip thumbnail (missing): notice={notice.pk}")
                )
                continue
            if old_size < min_bytes:
                continue

            with notice.thumbnail.open("rb") as fh:
                original = fh.read()
            compressed = compress_image_bytes(original, max_width=THUMBNAIL_MAX_WIDTH)
            if not compressed or len(compressed) >= old_size:
                continue

            delta = old_size - len(compressed)
            self.stdout.write(
                f"thumbnail notice={notice.pk} "
                f"{old_size / 1024:.0f}KB -> {len(compressed) / 1024:.0f}KB "
                f"({notice.title[:40]})"
            )
            if dry_run:
                saved += delta
                continue

            old_name = notice.thumbnail.name
            stem = os.path.splitext(os.path.basename(old_name))[0]
            notice.thumbnail.save(f"{stem}.jpg", ContentFile(compressed), save=True)
            if old_name != notice.thumbnail.name:
                default_storage.delete(old_name)
            saved += delta
        return saved

    def _recompress_inline(self, min_bytes: int, dry_run: bool) -> int:
        saved = 0
        try:
            _, filenames = default_storage.listdir("notices/inline")
        except FileNotFoundError:
            return 0

        for filename in sorted(filenames):
            if filename.lower().endswith(".gif"):
                continue
            path = f"notices/inline/{filename}"
            try:
                old_size = default_storage.size(path)
            except FileNotFoundError:
                continue
            if old_size < min_bytes:
                continue

            with default_storage.open(path, "rb") as fh:
                original = fh.read()
            compressed = compress_image_bytes(original, max_width=INLINE_MAX_WIDTH)
            if not compressed or len(compressed) >= old_size:
                continue

            delta = old_size - len(compressed)
            self.stdout.write(
                f"inline {path} {old_size / 1024:.0f}KB -> {len(compressed) / 1024:.0f}KB"
            )
            if dry_run:
                saved += delta
                continue

            stem = os.path.splitext(filename)[0]
            lower = filename.lower()
            if lower.endswith((".jpg", ".jpeg")):
                new_path = path
            else:
                new_path = f"notices/inline/{stem}.jpg"
            old_url = default_storage.url(path)
            new_url = default_storage.url(new_path)

            if new_path != path:
                default_storage.delete(path)
            default_storage.save(new_path, ContentFile(compressed))
            if old_url != new_url:
                self._rewrite_body_image_urls(old_url, new_url)
            saved += delta
        return saved

    def _rewrite_body_image_urls(self, old_url: str, new_url: str) -> None:
        for notice in Notice.objects.filter(body__contains=old_url).iterator():
            notice.body = notice.body.replace(old_url, new_url)
            notice.save(update_fields=["body"])
