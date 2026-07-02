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
_LIST_LINE_RE = re.compile(r"^(\s*)(?:(\d+\.)|([-*+]))\s+(.*)$")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)|_(.+?)_")
_DOUBLE_INLINE_CODE_RE = re.compile(r"``([^`]+)``")
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")


def _slugify_heading(text: str) -> str:
    plain = re.sub(r"\*\*|`", "", text).strip().lower()
    slug = re.sub(r"[^\w\s가-힣-]", "", plain)
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug or "section"


def extract_section_toc(text: str) -> list[tuple[str, str]]:
    """## 제목 목록 → (anchor, label) — 권한 문서 목차용."""
    body = _strip_frontmatter(text)
    toc: list[tuple[str, str]] = []
    seen: dict[str, int] = {}
    for match in re.finditer(r"^##\s+(.+)$", body, re.MULTILINE):
        label = re.sub(r"\*\*", "", match.group(1)).strip()
        base = _slugify_heading(label)
        count = seen.get(base, 0)
        seen[base] = count + 1
        anchor = base if count == 0 else f"{base}-{count + 1}"
        toc.append((anchor, label))
    return toc


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


def _is_list_block(block: str) -> bool:
    lines = [ln for ln in block.splitlines() if ln.strip()]
    return bool(lines) and all(_LIST_LINE_RE.match(ln) for ln in lines)


def _render_nested_list(block: str) -> str:
    items: list[tuple[int, str, str]] = []
    for line in block.splitlines():
        if not line.strip():
            continue
        match = _LIST_LINE_RE.match(line.rstrip())
        if not match:
            continue
        indent = len(match.group(1).expandtabs(4))
        kind = "ol" if match.group(2) else "ul"
        items.append((indent, kind, match.group(4)))

    if not items:
        return ""

    def build(start: int, base_indent: int) -> tuple[str, int]:
        chunks: list[str] = []
        index = start
        current_tag: str | None = None

        while index < len(items):
            indent, kind, text = items[index]
            if indent < base_indent:
                break
            if indent > base_indent:
                break

            if kind != current_tag:
                if current_tag:
                    chunks.append(f"</{current_tag}>")
                chunks.append(f"<{kind}>")
                current_tag = kind

            index += 1
            child_html = ""
            if index < len(items) and items[index][0] > indent:
                child_html, index = build(index, items[index][0])

            chunks.append(f"<li>{_render_inline(text)}{child_html}</li>")

        if current_tag:
            chunks.append(f"</{current_tag}>")
        return "".join(chunks), index

    html, _ = build(0, items[0][0])
    return html


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
    if _is_list_block(stripped):
        return _render_nested_list(stripped)
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

    heading_ids: dict[str, int] = {}

    def _header_repl(match: re.Match[str]) -> str:
        level = min(len(match.group(1)), 6)
        raw_title = match.group(2).strip()
        title = _render_inline(raw_title)
        base = _slugify_heading(raw_title)
        count = heading_ids.get(base, 0)
        heading_ids[base] = count + 1
        anchor = base if count == 0 else f"{base}-{count + 1}"
        key = f"@@H{len(placeholders)}@@"
        id_attr = f' id="{anchor}"' if level <= 2 else ""
        placeholders[key] = f"<h{level}{id_attr}>{title}</h{level}>"
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
