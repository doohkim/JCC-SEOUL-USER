# Cursor 정책 (JCC Seoul User)

이 폴더는 **Cursor AI**와 **팀원**이 같은 기준으로 작업하도록 하는 규칙·템플릿 모음입니다.

| 위치 | 대상 | 설명 |
|------|------|------|
| [rules/](rules/) | AI (자동) + 사람 (참고) | `.mdc` 규칙 파일 — Cursor가 컨텍스트로 로드 |
| [../AGENTS.md](../AGENTS.md) | AI (자동) | 저장소 루트 짧은 힌트 (자주 쓰는 경로·함수) |
| [../PROMPTS.md](../PROMPTS.md) | 사람 | 작업 유형별 프롬프트 템플릿 (`@UI`, `@PERM` 등) |

---

## 규칙 한눈에 보기

| 파일 | 적용 | `@` 태그 | 한 줄 요약 |
|------|------|----------|------------|
| [00-ai-usage.mdc](rules/00-ai-usage.mdc) | **항상** | — | AI 비용·안전·편집 워크플로 |
| [01-jcc-seoul-django.mdc](rules/01-jcc-seoul-django.mdc) | **항상** | — | Django 스택, 앱 구조, 실행 경로, 핵심 보안 |
| [10-jcc-drf-api.mdc](rules/10-jcc-drf-api.mdc) | API·시리얼라이저 편집 시 | — | DRF 폴더 구조, URL, permission 패턴 |
| [11-jcc-permissions.mdc](rules/11-jcc-permissions.mdc) | 권한·뷰·API 편집 시 | `@PERM` | 유저 타입별 권한 매트릭스, Plan 모드 질문 |
| [12-jcc-xlsx-importers.mdc](rules/12-jcc-xlsx-importers.mdc) | 임포터·import 명령 편집 시 | — | 엑셀 파싱, openpyxl, 명단·출석 워크북 |
| [13-jcc-frontend-ui.mdc](rules/13-jcc-frontend-ui.mdc) | 템플릿·CSS·JS 편집 시 | `@UI` `@RESPONSIVE` `@STATIC` | 토스풍 UI, 반응형, 정적 캐시 버스팅 |
| [14-jcc-testing.mdc](rules/14-jcc-testing.mdc) | Python 코드 편집 시 | `@TEST` | 기능·권한 변경 시 테스트 필수 |

**항상 적용** (`alwaysApply: true`): 대화마다 자동 로드.  
**조건부 적용** (`globs`): 해당 경로 파일을 다룰 때 추가 로드.

---

## 사람이 쓸 때 (빠른 시작)

1. **일반 코딩** — 별도 설정 없음. `00`·`01` 규칙이 AI에 항상 적용됩니다.
2. **Cursor에게 지시할 때** — [PROMPTS.md](../PROMPTS.md)에서 템플릿(A~F)을 복사하고, 작업에 맞는 `@` 태그를 붙입니다.
3. **권한·노출 범위 변경** — 먼저 [11-jcc-permissions.mdc](rules/11-jcc-permissions.mdc)의 유저 타입 매트릭스를 확인하고, Plan 모드에서 타입별 조회/쓰기를 질문합니다.
4. **규칙 수정** — `.mdc` 상단 YAML(`description`, `globs`, `alwaysApply`)을 바꾸면 Cursor 동작이 달라집니다. 본 README 표도 함께 갱신하세요.

---

## 파일 이름 규칙

```
00–09  항상 적용 (프로젝트 공통)
10–19  백엔드·도메인
20–29  (예약) 프론트·기타
```

새 규칙 추가 시 [rules/README.md](rules/README.md)와 이 표에 한 줄씩 등록합니다.

---

## 관련 문서

- Django 앱·실행: [app/README.md](../app/README.md)
- AI에게 짧은 힌트: [AGENTS.md](../AGENTS.md)
- 복붙 프롬프트: [PROMPTS.md](../PROMPTS.md)
