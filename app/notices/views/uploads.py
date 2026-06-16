"""공지 본문 인라인 이미지 업로드 엔드포인트 (TinyMCE).

- 공지 관리자(슈퍼유저·플랫폼 관리자·공지 관리 기능권한)만 업로드 가능.
- 이미지 MIME/확장자 화이트리스트 + Pillow 무결성 검증 + 용량 제한.
- CSRF 는 유지하며(에디터 핸들러가 csrfmiddlewaretoken 전송), 저장 경로는 MEDIA/notices/inline/.
"""

from __future__ import annotations

import uuid

from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from notices.services import compress_inline_image
from users.permissions import is_notice_manager

_ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB


@require_POST
def notice_image_upload(request):
    user = request.user
    if not user.is_authenticated or not is_notice_manager(user):
        return JsonResponse({"error": "권한이 없습니다."}, status=403)

    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"error": "파일이 없습니다."}, status=400)
    if upload.size > _MAX_UPLOAD_BYTES:
        return JsonResponse(
            {"error": "이미지는 5MB 이하만 업로드할 수 있습니다."}, status=400
        )
    ext = _ALLOWED_CONTENT_TYPES.get(upload.content_type)
    if not ext:
        return JsonResponse({"error": "지원하지 않는 이미지 형식입니다."}, status=400)

    try:
        from PIL import Image

        Image.open(upload).verify()
    except Exception:
        return JsonResponse({"error": "올바른 이미지 파일이 아닙니다."}, status=400)
    upload.seek(0)

    if upload.content_type != "image/gif":
        upload = compress_inline_image(upload)
        ext = "jpg"

    name = f"notices/inline/{uuid.uuid4().hex}.{ext}"
    saved = default_storage.save(name, upload)
    return JsonResponse({"location": default_storage.url(saved)})
