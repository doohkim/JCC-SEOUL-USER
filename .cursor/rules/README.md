# rules/ — Cursor 규칙 파일

`.mdc` = Markdown + YAML frontmatter. **Cursor만 자동 로드**하며, 사람은 [상위 README](../README.md)와 이 표를 보면 됩니다.

## 목록

| 파일 | `alwaysApply` | `globs` (요약) |
|------|:-------------:|----------------|
| `00-ai-usage.mdc` | ✅ | — |
| `01-jcc-seoul-django.mdc` | ✅ | — |
| `10-jcc-drf-api.mdc` | ❌ | `apis/`, `serializers/`, `services/`, `admin/` |
| `11-jcc-permissions.mdc` | ❌ | `permissions.py`, `apis/`, `views/` |
| `12-jcc-xlsx-importers.mdc` | ❌ | `importers/`, `management/commands/import*.py` |
| `13-jcc-frontend-ui.mdc` | ❌ | `templates/`, `static/**/*.css`, `static/**/*.js` |
| `14-jcc-testing.mdc` | ❌ | `app/**/*.py` |

## 새 규칙 추가 체크리스트

1. 번호 접두사 선택 (`00` 항상 / `10+` 조건부)
2. frontmatter: `description`, `globs`(필요 시), `alwaysApply`
3. 본문: 제목, **적용 시점**, 핵심 bullet (AI·사람 모두 읽기 쉽게)
4. [../README.md](../README.md) 표에 한 줄 추가
5. [PROMPTS.md](../../PROMPTS.md)에 `@` 태그가 있으면 매핑 행 추가
