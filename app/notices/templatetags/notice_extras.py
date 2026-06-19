import re
from datetime import timedelta

from django import template
from django.utils import timezone
from django.utils.safestring import mark_safe

register = template.Library()

_IMG_TAG_RE = re.compile(r"<img\b([^>]*?)>", re.IGNORECASE)

_NOTICE_NEW_DAYS = 7


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
    created_at = getattr(notice, "created_at", None)
    if not created_at:
        return False
    return created_at >= timezone.now() - timedelta(days=_NOTICE_NEW_DAYS)


@register.filter
def intcomma(value) -> str:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{n:,}"
