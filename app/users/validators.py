"""모델·폼용 검증기."""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError


def _korea_mobile_digits(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("82") and len(digits) >= 10:
        body = digits[2:]
        if not body.startswith("0"):
            body = "0" + body
        digits = body
    return digits


def normalize_korea_mobile_phone(value: str) -> str | None:
    """휴대폰 번호 검증·정규화. 빈 값은 ``""``, 유효하면 ``010-1234-5678`` 형태, 아니면 ``None``."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    digits = _korea_mobile_digits(raw)
    if not re.fullmatch(r"01[016789]\d{7,8}", digits):
        return None
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"


def validate_korea_mobile_phone(value: str) -> None:
    """
    한국 **휴대전화** 번호 형식 검증.

    - 비어 있으면 통과 (모델에서 ``blank=True``).
    - 허용 예: ``010-1234-5678``, ``01012345678``, ``+82 10-1234-5678``, ``82-10-1234-5678``
    """
    if value is None or not str(value).strip():
        return

    if normalize_korea_mobile_phone(str(value).strip()) is None:
        raise ValidationError(
            "휴대전화 형식이 아닙니다. 예: 010-1234-5678 또는 01012345678",
            code="invalid_mobile_phone",
        )
