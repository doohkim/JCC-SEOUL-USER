"""조장·부조장 사용 가이드 — 마크다운 로드·렌더."""

from __future__ import annotations

import html
import re
from pathlib import Path

from django.conf import settings
from django.templatetags.static import static
from django.utils.safestring import SafeString, mark_safe

from cursor_docs.services.markdown import render_markdown

_GUIDE_RELATIVE = "docs/retreat-leader-guide.md"
_STATIC_IMG = re.compile(r"!\[([^\]]*)\]\(retreat/guides/([^)]+)\)")
_IMAGE_ONLY = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", re.MULTILINE)


def guide_markdown_path() -> Path:
    return Path(settings.ROOT_DIR) / _GUIDE_RELATIVE


def load_leader_guide_markdown() -> str:
    path = guide_markdown_path()
    if not path.is_file():
        raise FileNotFoundError(f"가이드 문서를 찾을 수 없습니다: {path}")
    return path.read_text(encoding="utf-8")


def _resolve_static_images(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        alt = match.group(1)
        filename = match.group(2).strip()
        url = static(f"retreat/guides/{filename}")
        return f"![{alt}]({url})"

    return _STATIC_IMG.sub(repl, text)


def _inject_image_blocks(text: str) -> tuple[str, dict[str, str]]:
    placeholders: dict[str, str] = {}

    def repl(match: re.Match[str]) -> str:
        key = f"@@GUIDEIMG{len(placeholders)}@@"
        alt = html.escape(match.group(1))
        src = html.escape(match.group(2).strip(), quote=True)
        caption = (
            f'<figcaption class="jcc-retreat-guideCaption">{alt}</figcaption>'
            if alt
            else ""
        )
        placeholders[key] = (
            f'<figure class="jcc-retreat-guideFigure">'
            f'<img class="jcc-retreat-guideImg" src="{src}" alt="{alt}" loading="lazy">'
            f"{caption}</figure>"
        )
        return f"\n\n{key}\n\n"

    return _IMAGE_ONLY.sub(repl, text), placeholders


def _inject_section_ids(html_out: str) -> str:
    sections = (
        ("접근 권한", "guide-access"),
        ("1. 대시보드", "guide-dashboard"),
        ("2. 조 관리", "guide-groups"),
        ("3. 조원 리스트", "guide-members"),
        ("4. 조원 추가", "guide-member-form"),
        ("문의", "guide-contact"),
    )
    for prefix, section_id in sections:
        html_out = re.sub(
            rf"<h2>({re.escape(prefix)}[^<]*)</h2>",
            rf'<h2 id="{section_id}" class="jcc-retreat-guideSection">\1</h2>',
            html_out,
            count=1,
        )
    return html_out


def _strip_duplicate_header(html_out: str) -> str:
    """페이지 헤더와 중복되는 문서 최상단 제목·소개 문단 제거."""
    html_out = re.sub(r"^<h1>.*?</h1>\s*", "", html_out, count=1)
    html_out = re.sub(
        r"^<p>수련회 앱을 조장·부조장 권한으로 이용하는 방법을 안내합니다\.</p>\s*",
        "",
        html_out,
        count=1,
    )
    return html_out


def render_leader_guide(text: str) -> SafeString:
    resolved = _resolve_static_images(text)
    prepped, img_placeholders = _inject_image_blocks(resolved)
    html_out = str(render_markdown(prepped))
    for key, fragment in img_placeholders.items():
        html_out = html_out.replace(f"<p>{key}</p>", fragment)
        html_out = html_out.replace(key, fragment)
    html_out = _strip_duplicate_header(html_out)
    html_out = _inject_section_ids(html_out)
    return mark_safe(html_out)
