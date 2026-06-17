# 프롬프트 템플릿 (JCC Seoul User)

이 파일은 Cursor에게 지시할 때 **복붙해서 채우는** 템플릿 모음입니다.  
표준 규칙은 [`.cursor/rules/`](.cursor/rules/)에 있으며, 전체 목차는 [`.cursor/README.md`](.cursor/README.md)를 참고하세요.

| 태그 | 규칙 파일 |
|------|-----------|
| `@UI` `@RESPONSIVE` `@STATIC` | `.cursor/rules/13-jcc-frontend-ui.mdc` |
| `@TEST` | `.cursor/rules/14-jcc-testing.mdc` |
| `@PERM` | `.cursor/rules/11-jcc-permissions.mdc` |

**사용법**: 작업 유형 템플릿(A~F)을 복사 → `[]` 안을 채움 → 적용 표준에 필요한 `@` 태그를 명시 → 전송.

---

## 공통 필드 (모든 템플릿)

```
목표:
대상 파일·심볼:
동작:
적용 표준: @UI @RESPONSIVE @PERM @TEST 중 선택
범위 제외:
검증:
```

---

## A. 기능·화면 구현

```
목표: [한 줄]
대상 파일·심볼: [예: app/templates/retreat/pickup.html, app/retreat/static/retreat/pickup.js]
동작:
- [사용자가 보는 변화]
- [API/저장 동작]
적용 표준: @UI @RESPONSIVE @TEST
범위 제외: [리팩터·다른 화면 수정 금지 등]
검증: cd app && poetry run python manage.py test retreat -v 1
```

---

## B. 버그 수정

```
목표: [버그 한 줄 요약]
재현: [어디서 / 어떤 조작 / 기대 vs 실제]
대상 파일·심볼: [추정 파일]
동작: [수정 후 기대 동작]
적용 표준: @TEST
범위 제외:
검증: [테스트 명령 + 수동 확인]
```

---

## C. 권한 변경·추가

```
목표: [권한 변경 요약]
대상 유저 타입: [슈퍼유저 / 목사·전도사 / 회장단 / 조장·부조장 / 일반 …]
관련 함수: [예: can_manage_retreat_pickup, visible_retreat_groups_for]
대상 파일·심볼: [permissions.py, apis/, views/, tests/]
동작:
- [타입별 조회 범위]
- [타입별 변경(쓰기) 가능 여부]
적용 표준: @PERM @TEST
범위 제외:
검증: cd app && poetry run python manage.py test retreat.tests.test_permissions -v 1
```

> Plan 모드에서는 `@PERM`에 따라 **전체 유저 타입 매트릭스**로 먼저 확인한다.

---

## D. 작은 리팩터·정리

```
목표: [한 줄]
대상 파일·심볼: [1~3개 파일만]
동작: [최소 diff로 할 일]
적용 표준: (없음 또는 @STATIC)
범위 제외: [동작 변경·다른 앱 수정 금지]
검증: manage.py check
```

---

## E. 조사·진단 (편집 금지)

```
목표: [알고 싶은 것]
대상 파일·심볼: [좁힌 범위]
질문:
- [구체적 질문 1]
- [구체적 질문 2]
범위 제외: 파일 편집 금지, 결론만
```

---

## F. DRF API 추가·변경

```
목표: [엔드포인트 한 줄]
대상 파일·심볼: [app/<app>/apis/, serializers/, urls.py]
동작:
- Method / URL:
- Request / Response 필드:
- permission_classes:
적용 표준: @PERM @TEST
범위 제외: [기존 API 계약 변경 여부]
검증: cd app && poetry run python manage.py test <app> -v 1
```

---

## 채운 예시 — 픽업 폼 인라인 검증

```
목표: 픽업 등록 모달에서 필수값 누락 시 팝업 없이 필드별 안내
대상 파일·심볼:
- app/retreat/static/retreat/pickup.js (markInvalid, form submit)
- app/retreat/static/retreat/retreat.css (.is-invalid, .jcc-field-error)
- app/templates/retreat/pickup.html
동작:
- 이름·열차 시각·탑승장소·연락처 비었을 때 빨간 테두리 + 안내문구
- datetime 피커(.jcc-dtp-field)에도 is-invalid 표시
- 첫 오류 필드로 포커스, 입력 시 표시 제거
- 연락처 형식 오류도 동일 패턴
적용 표준: @UI @STATIC @TEST
범위 제외: API·권한·다른 모달 수정 금지
검증:
- cd app && poetry run python manage.py check
- 픽업 모달에서 빈 등록 → 인라인 표시 확인
- css/js ?v= 버전 갱신
```
