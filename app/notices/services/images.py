"""공지 썸네일 이미지 리사이즈/압축.

업로드된 원본을 그대로 저장하면 목록·상세에서 수 MB 이미지를 그대로 내려받아
로딩이 느려진다. 업로드 시점에 최대 폭으로 축소하고 JPEG로 재인코딩해
전송량을 줄인다.
"""

from __future__ import annotations

import io
import os

from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps

MAX_WIDTH = 1200  # 카드·배너 표시에 충분한 폭
JPEG_QUALITY = 82


def compress_thumbnail(upload):
    """업로드 이미지를 리사이즈/압축한 새 파일로 반환한다.

    실패하거나 처리할 필요가 없으면 원본 `upload`을 그대로 돌려준다.
    """
    try:
        upload.seek(0)
        image = Image.open(upload)
        # EXIF 방향 보정 (휴대폰 사진 회전 문제 방지)
        image = ImageOps.exif_transpose(image)
        # 투명도/팔레트는 흰 배경으로 평탄화 후 RGB 변환
        if image.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            rgba = image.convert("RGBA")
            background.paste(rgba, mask=rgba.split()[-1])
            image = background
        else:
            image = image.convert("RGB")

        if image.width > MAX_WIDTH:
            ratio = MAX_WIDTH / float(image.width)
            new_size = (MAX_WIDTH, int(image.height * ratio))
            image = image.resize(new_size, Image.LANCZOS)

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        buffer.seek(0)
    except Exception:
        upload.seek(0)
        return upload

    base, _ = os.path.splitext(os.path.basename(getattr(upload, "name", "thumbnail")))
    new_name = f"{base or 'thumbnail'}.jpg"
    return InMemoryUploadedFile(
        buffer,
        field_name=getattr(upload, "field_name", "thumbnail"),
        name=new_name,
        content_type="image/jpeg",
        size=buffer.getbuffer().nbytes,
        charset=None,
    )
