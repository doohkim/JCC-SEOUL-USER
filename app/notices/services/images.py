"""공지 이미지 리사이즈/압축.

업로드된 원본을 그대로 저장하면 목록·상세에서 수 MB 이미지를 그대로 내려받아
로딩이 느려진다. 업로드·일괄 재처리 시 최대 폭으로 축소하고 JPEG로 재인코딩한다.
"""

from __future__ import annotations

import io
import os

from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps

THUMBNAIL_MAX_WIDTH = 1200  # 카드·배너 표시에 충분한 폭
INLINE_MAX_WIDTH = 1600  # 본문 인라인 이미지
JPEG_QUALITY = 82


def compress_image_bytes(data: bytes, *, max_width: int) -> bytes | None:
    """이미지 바이트를 JPEG로 리사이즈/압축한다. GIF·실패 시 None."""
    try:
        image = Image.open(io.BytesIO(data))
        if image.format == "GIF":
            return None
        image = ImageOps.exif_transpose(image)
        if image.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            rgba = image.convert("RGBA")
            background.paste(rgba, mask=rgba.split()[-1])
            image = background
        else:
            image = image.convert("RGB")

        if image.width > max_width:
            ratio = max_width / float(image.width)
            new_size = (max_width, int(image.height * ratio))
            image = image.resize(new_size, Image.LANCZOS)

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return buffer.getvalue()
    except Exception:
        return None


def _as_uploaded_file(
    upload,
    compressed: bytes,
    *,
    field_name: str,
    default_stem: str,
) -> InMemoryUploadedFile:
    base, _ = os.path.splitext(os.path.basename(getattr(upload, "name", default_stem)))
    new_name = f"{base or default_stem}.jpg"
    buffer = io.BytesIO(compressed)
    return InMemoryUploadedFile(
        buffer,
        field_name=field_name,
        name=new_name,
        content_type="image/jpeg",
        size=len(compressed),
        charset=None,
    )


def _compress_upload(upload, *, max_width: int, field_name: str, default_stem: str):
    try:
        upload.seek(0)
        original = upload.read()
        compressed = compress_image_bytes(original, max_width=max_width)
        if compressed is None or len(compressed) >= len(original):
            upload.seek(0)
            return upload
        return _as_uploaded_file(
            upload, compressed, field_name=field_name, default_stem=default_stem
        )
    except Exception:
        upload.seek(0)
        return upload


def compress_thumbnail(upload):
    """썸네일 업로드 파일을 리사이즈/압축한다."""
    return _compress_upload(
        upload,
        max_width=THUMBNAIL_MAX_WIDTH,
        field_name=getattr(upload, "field_name", "thumbnail"),
        default_stem="thumbnail",
    )


def compress_inline_image(upload):
    """본문 인라인 이미지 업로드 파일을 리사이즈/압축한다."""
    return _compress_upload(
        upload,
        max_width=INLINE_MAX_WIDTH,
        field_name=getattr(upload, "field_name", "file"),
        default_stem="inline",
    )
