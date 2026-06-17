"""휴대폰 번호 표시용 템플릿 필터."""

from django import template

from users.validators import normalize_korea_mobile_phone

register = template.Library()


@register.filter(name="format_korea_phone")
def format_korea_phone(value) -> str:
    """저장된 연락처를 ``010-1234-5678`` 형태로 표시. 비어 있으면 ``-``."""
    raw = str(value or "").strip()
    if not raw:
        return "-"
    normalized = normalize_korea_mobile_phone(raw)
    return normalized if normalized is not None else raw
