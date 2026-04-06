"""drf-spectacular — OpenAPI 3 스키마·Swagger UI."""

SPECTACULAR_SETTINGS = {
    "TITLE": "JCC Seoul User API",
    "DESCRIPTION": "출석·교적·계정 등 REST API (세션/토큰·연동 서비스 키).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/",
    "TAGS": [
        {"name": "attendance", "description": "출석 (부서·팀·주차·명단)"},
        {"name": "registry", "description": "교적·조직 (멤버·가족·방문·이적)"},
        {"name": "counseling", "description": "상담 (상담사·요청)"},
        {"name": "users", "description": "계정·외부 연동 (역할·연동 API)"},
        {"name": "docs", "description": "OpenAPI 스키마·Swagger UI"},
        {"name": "other", "description": "기타 (경로 규칙 미매칭)"},
    ],
    "POSTPROCESSING_HOOKS": [
        "config.openapi_hooks.postprocess_schema_tags",
    ],
}
