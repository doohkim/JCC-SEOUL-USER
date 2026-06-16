import re

from django import template
from django.utils.safestring import mark_safe

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
