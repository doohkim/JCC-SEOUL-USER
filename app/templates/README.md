# 프로젝트 템플릿 (`BASE_DIR / templates`)

앱(`users/`) 밖에서 전역·관리자 템플릿을 둡니다.

- `admin/users/` — 사용자·조직 이동 등 커스텀 Admin 화면

`config/settings.py`의 `TEMPLATES["DIRS"]`에 이 상위 폴더(`templates`)가 등록되어 있습니다.
