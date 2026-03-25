"""카카오 알림톡 등 외부 알림 (스텁)."""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def notify_new_counseling_request(request_obj, *, absolute_detail_url: str) -> None:
    """
    신청 생성 시 상담사에게 알림.
    실제 알림톡은 카카오 비즈니스 채널·템플릿 승인 후 REST 연동.
    """
    if not getattr(settings, "COUNSELING_KAKAO_ALIMTALK_ENABLED", False):
        logger.info(
            "counseling notify (stub): request=%s url=%s",
            getattr(request_obj, "public_id", None),
            absolute_detail_url,
        )
        return
    # 향후: settings.COUNSELING_KAKAO_* 키로 발송
    logger.warning("COUNSELING_KAKAO_ALIMTALK_ENABLED is on but sender is not implemented")
