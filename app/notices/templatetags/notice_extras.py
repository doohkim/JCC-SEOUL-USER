import re

from django import template
from django.utils.safestring import mark_safe

from notices.services.newness import has_notices_created_today, is_created_today

register = template.Library()

_IMG_TAG_RE = re.compile(r"<img\b([^>]*?)>", re.IGNORECASE)


def _add_lazy_loading(match: re.Match[str]) -> str:
    attrs = match.group(1)
    if re.search(r"\bloading\s*=", attrs, re.IGNORECASE):
        return match.group(0)
    return f'<img loading="lazy"{attrs}>'


@register.filter(is_safe=True)
def lazy_images(value: str) -> str:
    if not value:
        return value
    return mark_safe(_IMG_TAG_RE.sub(_add_lazy_loading, value))


@register.filter
def is_notice_new(notice) -> bool:
    """이야기 카드 NEW — 작성일이 로컬 당일인 경우."""
    return is_created_today(getattr(notice, "created_at", None))


@register.simple_tag
def notices_has_new_today() -> bool:
    """좌측 네비 등 — 당일 등록된 이야기가 하나라도 있으면 True."""
    return has_notices_created_today()


@register.filter
def intcomma(value) -> str:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{n:,}"
