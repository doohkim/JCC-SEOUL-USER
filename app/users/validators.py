"""모델·폼용 검증기."""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError


def validate_korea_mobile_phone(value: str) -> None:
    """
    한국 **휴대전화** 번호 형식 검증.

    - 비어 있으면 통과 (모델에서 ``blank=True``).
    - 허용 예: ``010-1234-5678``, ``01012345678``, ``+82 10-1234-5678``, ``82-10-1234-5678``
    """
    if value is None or not str(value).strip():
        return

    raw = str(value).strip()
    digits = re.sub(r"\D", "", raw)

    # +82 / 82 국가번호 → 국내 0으로 시작하도록
    if digits.startswith("82") and len(digits) >= 10:
        body = digits[2:]
        if not body.startswith("0"):
            body = "0" + body
        digits = body

    # 10xxxxxxxx (지역번호 등) 은 휴대폰이 아니므로 거절
    if not re.fullmatch(r"01[016789]\d{7,8}", digits):
        raise ValidationError(
            "휴대전화 형식이 아닙니다. 예: 010-1234-5678 또는 01012345678",
            code="invalid_mobile_phone",
        )
