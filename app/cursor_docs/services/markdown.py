from __future__ import annotations

import html
import re

from django.utils.safestring import mark_safe

_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
_FENCE_RE = re.compile(r"```(?:[\w+-]*)?\r?\n(.*?)```", re.DOTALL)
_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_HR_RE = re.compile(r"^(\*{3,}|-{3,}|_{3,})\s*$", re.MULTILINE)
_BLOCKQUOTE_RE = re.compile(r"^>\s?", re.MULTILINE)
_UL_ITEM_RE = re.compile(r"^[-*]\s+")
_OL_ITEM_RE = re.compile(r"^\d+\.\s+")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)|_(.+?)_")
_DOUBLE_INLINE_CODE_RE = re.compile(r"``([^`]+)``")
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")


def _strip_frontmatter(text: str) -> str:
    return _FRONTMATTER_RE.sub("", text, count=1)


def _escape(text: str) -> str:
    return html.escape(text, quote=True)


def _render_inline(text: str) -> str:
    """인라인 Markdown → HTML (본문은 escape 후 의미 있는 태그만 삽입)."""
    placeholders: dict[str, str] = {}

    def _code(match: re.Match[str]) -> str:
        key = f"@@IC{len(placeholders)}@@"
        placeholders[key] = (
            f'<code class="jcc-cursorDocs-inlineCode">{_escape(match.group(1))}</code>'
        )
        return key

    raw = _DOUBLE_INLINE_CODE_RE.sub(_code, text)
    raw = _INLINE_CODE_RE.sub(_code, raw)

    def _link(match: re.Match[str]) -> str:
        key = f"@@LK{len(placeholders)}@@"
        label = _escape(match.group(1))
        href = html.escape(match.group(2).strip(), quote=True)
        placeholders[key] = (
            f'<a href="{href}" target="_blank" rel="noopener noreferrer">{label}</a>'
        )
        return key

    raw = _LINK_RE.sub(_link, raw)

    def _bold(match: re.Match[str]) -> str:
        key = f"@@BD{len(placeholders)}@@"
        placeholders[key] = f"<strong>{_escape(match.group(1))}</strong>"
        return key

    raw = _BOLD_RE.sub(_bold, raw)

    def _italic(match: re.Match[str]) -> str:
        key = f"@@IT{len(placeholders)}@@"
        segment = match.group(1) or match.group(2) or ""
        placeholders[key] = f"<em>{_escape(segment)}</em>"
        return key

    raw = _ITALIC_RE.sub(_italic, raw)

    escaped = _escape(raw)
    for key, value in placeholders.items():
        escaped = escaped.replace(key, value)
    return escaped


def _paragraph_html(text: str) -> str:
    """단일 블록 내 줄바꿈은 <br>로 (escape 이후 삽입)."""
    lines = [line.strip() for line in text.splitlines()]
    parts = [_render_inline(line) for line in lines if line]
    if not parts:
        return ""
    return f"<p>{'<br>'.join(parts)}</p>"


def _is_table_block(block: str) -> bool:
    rows = [row.strip() for row in block.splitlines() if row.strip()]
    if len(rows) < 2:
        return False
    if not rows[0].startswith("|"):
        return False
    sep = rows[1].replace("|", "").strip()
    return bool(sep) and set(sep) <= {"-", ":", " "}


def _render_table(block: str) -> str:
    rows = [row.strip() for row in block.splitlines() if row.strip()]
    head_cells = [c.strip() for c in rows[0].strip("|").split("|")]
    body_rows = rows[2:]
    thead = "".join(f"<th>{_render_inline(c)}</th>" for c in head_cells)
    tbody_parts: list[str] = []
    for row in body_rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        tds = "".join(f"<td>{_render_inline(c)}</td>" for c in cells)
        tbody_parts.append(f"<tr>{tds}</tr>")
    tbody = "".join(tbody_parts)
    return (
        '<div class="jcc-cursorDocs-tableWrap"><table class="jcc-cursorDocs-table">'
        f"<thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>"
    )


def _is_ul_block(block: str) -> bool:
    lines = [ln for ln in block.splitlines() if ln.strip()]
    return bool(lines) and all(_UL_ITEM_RE.match(ln.strip()) for ln in lines)


def _is_ol_block(block: str) -> bool:
    lines = [ln for ln in block.splitlines() if ln.strip()]
    return bool(lines) and all(_OL_ITEM_RE.match(ln.strip()) for ln in lines)


def _render_ul(block: str) -> str:
    items = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        item = _UL_ITEM_RE.sub("", stripped, count=1).strip()
        items.append(f"<li>{_render_inline(item)}</li>")
    return f"<ul>{''.join(items)}</ul>"


def _render_ol(block: str) -> str:
    items = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        item = _OL_ITEM_RE.sub("", stripped, count=1).strip()
        items.append(f"<li>{_render_inline(item)}</li>")
    return f"<ol>{''.join(items)}</ol>"


def _render_blockquote(block: str) -> str:
    lines = []
    for line in block.splitlines():
        lines.append(_BLOCKQUOTE_RE.sub("", line).strip())
    inner = _paragraph_html("\n".join(lines))
    inner = inner.removeprefix("<p>").removesuffix("</p>")
    return f"<blockquote class=\"jcc-cursorDocs-blockquote\"><p>{inner}</p></blockquote>"


def _render_block(block: str) -> str:
    stripped = block.strip()
    if not stripped:
        return ""

    if stripped.startswith("@@CODE") or stripped.startswith("@@H"):
        return stripped

    if _is_table_block(stripped):
        return _render_table(stripped)
    if _is_ul_block(stripped):
        return _render_ul(stripped)
    if _is_ol_block(stripped):
        return _render_ol(stripped)
    if all(_BLOCKQUOTE_RE.match(ln) for ln in stripped.splitlines() if ln.strip()):
        return _render_blockquote(stripped)

    return _paragraph_html(stripped)


def render_markdown(text: str) -> str:
    """Markdown subset → HTML (Cursor docs 읽기 전용, 의존성 없음)."""
    body = _strip_frontmatter(text)
    placeholders: dict[str, str] = {}

    def _code_repl(match: re.Match[str]) -> str:
        key = f"@@CODE{len(placeholders)}@@"
        code = _escape(match.group(1).rstrip("\n"))
        placeholders[key] = (
            f'<pre class="jcc-cursorDocs-pre"><code>{code}</code></pre>'
        )
        return f"\n\n{key}\n\n"

    body = _FENCE_RE.sub(_code_repl, body)
    body = _HR_RE.sub("\n\n@@HR@@\n\n", body)

    def _header_repl(match: re.Match[str]) -> str:
        level = min(len(match.group(1)), 6)
        title = _render_inline(match.group(2).strip())
        key = f"@@H{len(placeholders)}@@"
        placeholders[key] = f"<h{level}>{title}</h{level}>"
        return f"\n\n{key}\n\n"

    body = _HEADER_RE.sub(_header_repl, body)

    blocks = re.split(r"\n\s*\n", body)
    html_parts: list[str] = []
    for block in blocks:
        piece = block.strip()
        if not piece:
            continue
        if piece == "@@HR@@":
            html_parts.append('<hr class="jcc-cursorDocs-hr">')
            continue
        html_parts.append(_render_block(piece))

    rendered = "\n".join(part for part in html_parts if part)

    for key, value in placeholders.items():
        rendered = rendered.replace(key, value)

    return mark_safe(rendered)
