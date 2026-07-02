from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.conf import settings

CATEGORY_POLICY = "policy"
CATEGORY_TEMPLATE = "template"
CATEGORY_PERMISSIONS = "permissions"

_TEMPLATE_RELATIVE_PATHS = (
    "PROMPTS.md",
    "docs/cursor-prompt-templates.md",
)

_PERMISSIONS_RELATIVE_PATHS = (
    "docs/retreat-council-permissions.md",
)

CATEGORY_DETAIL_URL_NAMES = {
    CATEGORY_POLICY: "cursor_docs_policy_detail",
    CATEGORY_TEMPLATE: "cursor_docs_template_detail",
    CATEGORY_PERMISSIONS: "cursor_docs_permissions_detail",
}

CATEGORY_LIST_URL_NAMES = {
    CATEGORY_POLICY: "cursor_docs_policy_list",
    CATEGORY_TEMPLATE: "cursor_docs_template_list",
    CATEGORY_PERMISSIONS: "cursor_docs_permissions_list",
}

_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_ALWAYS_APPLY_RE = re.compile(r"^alwaysApply:\s*(true|false)\s*$", re.MULTILINE)
_DESCRIPTION_RE = re.compile(r"^description:\s*(.+)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class DocEntry:
    slug: str
    category: str
    title: str
    relative_path: str
    excerpt: str
    badge: str
    modified_at: datetime | None


def _repo_root() -> Path:
    return Path(settings.ROOT_DIR)


def _policy_root() -> Path:
    return _repo_root() / ".cursor"


def _encode_slug(relative_path: str) -> str:
    return base64.urlsafe_b64encode(relative_path.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_slug(slug: str) -> str:
    padding = "=" * (-len(slug) % 4)
    return base64.urlsafe_b64decode(slug + padding).decode("utf-8")


def _strip_frontmatter(text: str) -> tuple[str, str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return text, ""
    return text[match.end() :], text[: match.end()]


def _title_from_content(body: str, relative_path: str) -> str:
    match = _TITLE_RE.search(body)
    if match:
        return match.group(1).strip()
    stem = Path(relative_path).stem
    if stem == "README":
        return Path(relative_path).parent.name or "README"
    return stem.replace("-", " ").replace("_", " ")


def _badge_from_frontmatter(frontmatter: str, category: str) -> str:
    if category == CATEGORY_TEMPLATE:
        return "템플릿"
    if category == CATEGORY_PERMISSIONS:
        return "수련회 권한"
    if not frontmatter:
        return "문서"
    if _ALWAYS_APPLY_RE.search(frontmatter):
        return "항상 적용"
    desc = _DESCRIPTION_RE.search(frontmatter)
    if desc:
        return desc.group(1).strip()[:40]
    return "규칙"


def _excerpt(body: str, limit: int = 140) -> str:
    lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("```"):
            continue
        cleaned = re.sub(r"[#*`>\[\]()]", "", stripped)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned:
            lines.append(cleaned)
        if len(" ".join(lines)) >= limit:
            break
    text = " ".join(lines)
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def _resolve_allowed_path(category: str, relative_path: str) -> Path | None:
    root = _repo_root()
    if category == CATEGORY_POLICY:
        base = _policy_root()
        candidate = (base / relative_path).resolve()
        try:
            candidate.relative_to(base.resolve())
        except ValueError:
            return None
        if candidate.suffix.lower() not in {".md", ".mdc"}:
            return None
        return candidate if candidate.is_file() else None

    if category == CATEGORY_TEMPLATE:
        if relative_path not in _TEMPLATE_RELATIVE_PATHS:
            return None
        candidate = (root / relative_path).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            return None
        return candidate if candidate.is_file() else None

    if category == CATEGORY_PERMISSIONS:
        if relative_path not in _PERMISSIONS_RELATIVE_PATHS:
            return None
        candidate = (root / relative_path).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            return None
        if candidate.suffix.lower() not in {".md", ".mdc"}:
            return None
        return candidate if candidate.is_file() else None

    return None


def _entry_from_path(category: str, relative_path: str, absolute: Path) -> DocEntry:
    raw = absolute.read_text(encoding="utf-8")
    body, frontmatter = _strip_frontmatter(raw)
    stat = absolute.stat()
    return DocEntry(
        slug=_encode_slug(relative_path),
        category=category,
        title=_title_from_content(body, relative_path),
        relative_path=relative_path,
        excerpt=_excerpt(body),
        badge=_badge_from_frontmatter(frontmatter, category),
        modified_at=datetime.fromtimestamp(stat.st_mtime),
    )


def list_docs(category: str) -> list[DocEntry]:
    entries: list[DocEntry] = []

    if category == CATEGORY_POLICY:
        base = _policy_root()
        if not base.is_dir():
            return []
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".md", ".mdc"}:
                continue
            rel = path.relative_to(base).as_posix()
            entries.append(_entry_from_path(category, rel, path))

    elif category == CATEGORY_TEMPLATE:
        root = _repo_root()
        for rel in _TEMPLATE_RELATIVE_PATHS:
            absolute = root / rel
            if absolute.is_file():
                entries.append(_entry_from_path(category, rel, absolute))

    elif category == CATEGORY_PERMISSIONS:
        root = _repo_root()
        for rel in _PERMISSIONS_RELATIVE_PATHS:
            absolute = root / rel
            if absolute.is_file():
                entries.append(_entry_from_path(category, rel, absolute))

    entries.sort(key=lambda item: item.relative_path)
    return entries


def get_doc(category: str, slug: str) -> tuple[DocEntry, str] | None:
    try:
        relative_path = _decode_slug(slug)
    except (ValueError, UnicodeDecodeError):
        return None

    absolute = _resolve_allowed_path(category, relative_path)
    if absolute is None:
        return None

    raw = absolute.read_text(encoding="utf-8")
    entry = _entry_from_path(category, relative_path, absolute)
    return entry, raw
