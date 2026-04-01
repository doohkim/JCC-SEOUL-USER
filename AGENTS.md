# Agent hints (JCC Seoul User)

- **할 일 목록**: TodoWrite 항목 설명은 **한글**로 작성한다 (`.cursor/rules/jcc-seoul-django.mdc`와 동일).
- **권한**: `users/permissions.py` — 출석·부서 목록은 `visible_divisions_for`(소속 Division만). 교적은 `can_access_member_registry`(목사·전도사). API/Admin 추가 시 반드시 이 계층을 따른다.
- **부서·팀 드롭다운 규칙**: 부서는 `membership_divisions_for(user)` (DB 소속 부서만), 팀은 `visible_teams_for(user, division)` 사용. 목사/전도사/플랫폼 관리자는 해당 부서 전체 팀, 그 외는 본인 소속 팀만.
- **큰 탐색**: 교적·출석·엑셀 임포트 흐름은 `registry`, `attendance`, `users` 세 앱에 걸려 있다. “어디서 처리되는지” 찾을 때는 `importers/` → `management/commands/` → `models/` → **`apis/`**(DRF) / **`views/`**(템플릿) 순으로 추적한다.
- **엑셀/명단**: 파싱 로직은 `app/registry/importers/`, `app/attendance/importers/`가 단일 진실에 가깝다. 커맨드는 얇게 유지하는 편이 맞다.
- **API**: `api/v1/attendance/…` 는 `app/attendance/urls.py`, `api/v1/org/…` 는 `app/registry/urls.py`. `config/urls.py` 는 앱별 `urls.py` 만 include 한다.
- **실행**: Django는 `app/manage.py` 기준 (`cd app && poetry run python manage.py …`).
