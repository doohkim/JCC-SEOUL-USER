"""
drf-spectacular 후처리 — URL 경로로 OpenAPI tag 를 Django 앱과 맞춤.

``/api/v1/<segment>/...`` 가 어느 앱 ``urls`` 에 속하는지에 따라 분기한다.
"""

from __future__ import annotations

_HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options"})

# (경로 접두사, OpenAPI tag 이름). 긴 접두사를 먼저 두어 더 구체적인 규칙이 우선한다.
_PATH_TAG_RULES: tuple[tuple[str, str], ...] = tuple(
    sorted(
        (
            ("/api/v1/attendance/", "attendance"),
            ("/api/v1/counseling/", "counseling"),
            ("/api/v1/integration/", "users"),
            ("/api/v1/users/", "users"),
            ("/api/v1/org/", "registry"),
            ("/api/v1/member/", "registry"),
            ("/api/v1/family/", "registry"),
            ("/api/v1/visits/", "registry"),
            ("/api/schema/", "docs"),
            ("/api/schema", "docs"),
        ),
        key=lambda x: len(x[0]),
        reverse=True,
    )
)


def _tag_for_path(path: str) -> str:
    if not path.startswith("/"):
        path = f"/{path}"
    for prefix, tag in _PATH_TAG_RULES:
        if path.startswith(prefix):
            return tag
    return "other"


def postprocess_schema_tags(result, generator, request, public):
    paths = result.get("paths")
    if not isinstance(paths, dict):
        return result

    for _path_key, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            operation["tags"] = [_tag_for_path(_path_key)]

    return result
