# 카카오 로그인 설정 가이드

사용자 페이지(`attendance`, `registry`)는 카카오 로그인으로만 접근합니다.
관리자 페이지(`django-admin`)는 기존 Django 관리자 로그인 방식을 그대로 사용합니다.

## 서브도메인 분리 (운영 권장)

- 앱(UI): `https://shalom.jcc-seoul.com`
- Django Admin: `https://shalom.admin.jcc-seoul.com/django-admin/`
- API: `https://shalom.api.jcc-seoul.com`
- 문서: `https://shalom.docs.jcc-seoul.com/docs/`

환경 변수:

- `APP_HOST=shalom.jcc-seoul.com`
- `ADMIN_HOST=shalom.admin.jcc-seoul.com`
- `API_HOST=shalom.api.jcc-seoul.com`
- `DOCS_HOST=shalom.docs.jcc-seoul.com`
- `SUBDOMAIN_ROUTING_ENABLED=true`

`SUBDOMAIN_ROUTING_ENABLED=true`일 때 호스트별 접근 경로를 강제합니다.

## 1) 카카오 개발자 콘솔 설정

1. [카카오 개발자](https://developers.kakao.com/)에서 애플리케이션 생성
2. 플랫폼 -> Web 설정
   - 사이트 도메인(로컬): `http://127.0.0.1:8000`, `http://localhost:8000`
3. 제품 설정 -> 카카오 로그인 -> 활성화
4. Redirect URI 등록
   - 로컬: `http://127.0.0.1:8000/auth/complete/kakao/`
   - 운영: `https://shalom.jcc-seoul.com/auth/complete/kakao/`
5. 동의항목 설정
   - 닉네임(프로필 정보) 동의
   - 이메일 동의(가능하면 활성화)

## 2) 환경 변수 설정

아래 값을 실행 환경에 설정합니다.

- `KAKAO_REST_API_KEY` : 카카오 REST API 키
- `KAKAO_CLIENT_SECRET` : 카카오 Client Secret (사용 시)
- `KAKAO_REDIRECT_URI` : 콜백 URI (예: `https://shalom.jcc-seoul.com/auth/complete/kakao/`)

`.env` 자동 로드를 지원합니다. 아래 위치 중 하나에 넣으면 됩니다.

- 프로젝트 루트: `/.env`
- Django 루트: `/app/.env`

예시:

```bash
export KAKAO_REST_API_KEY="카카오REST키"
export KAKAO_CLIENT_SECRET="카카오시크릿"
export KAKAO_REDIRECT_URI="http://127.0.0.1:8000/auth/complete/kakao/"
```

## 3) 실행 및 마이그레이션

```bash
cd app
poetry run python manage.py migrate
poetry run python manage.py runserver
```

## 4) 동작 확인

1. `http://127.0.0.1:8000/login/` 접속
2. `카카오로 로그인 / 회원가입` 클릭
3. 카카오 인증 후 `/attendance/`로 이동
4. 최초 로그인 사용자는 내부 사용자 계정이 자동 생성됨(`username`: `kakao_<uid>`)

## 5) 소속 승인 온보딩 흐름

1. 최초 카카오 로그인 사용자는 `소속 신청` 페이지(`/onboarding/`)로 이동
2. 사용자가 희망 부서/팀을 제출하면 상태가 `승인 대기`로 저장
3. 관리자는 Django Admin 사용자 목록에서 온보딩 대기자를 선택해 승인/반려 처리
4. 승인 시 `UserDivisionTeam` 기본 소속이 자동 생성되고, 이후 운영 화면 접근 가능

## 5-1) 출석 권한 분리 운영

- 전체 관리자: `is_staff` 또는 `is_superuser` (Django admin 포함)
- 출석부 관리자: `Role.code=attendance_admin` 부여 사용자
- 팀장/셀장: `team_leader`, `cell_leader`

권장 운영:

1. 조직도 시드로 `attendance_admin` 역할 생성
   ```bash
   cd app
   poetry run python manage.py seed_org_chart
   ```
2. 사용자 직책 부여 화면에서 부서별로 권한 설정
   - 경로: `/accounts/roles/`
   - 목사: 담당 부서 선택 가능(다중 담당 지원)
   - 전도사: 본인 담당 1개 부서 고정
3. 출석부 전체 권한이 필요하면 해당 사용자에게 `attendance_admin` 체크

참고:

- “필요 시 시드 데이터에 attendance_admin 역할 자동 생성”은
  초기 데이터 입력 명령(`seed_org_chart`) 실행 시 `attendance_admin` 코드가 자동 준비된다는 의미입니다.

## 5-2) 주차권 신청/관리

- 일반 사용자:
  - `주차권` 단일 탭에서 상단 탭(내 신청/관리 목록) 사용
  - 차량번호로 신청
  - 본인 신청 내역 조회
  - 차량번호 수정/삭제 가능
  - 경로: `/attendance/parking/`

- 주차장 관리자(`parking_admin` 또는 플랫폼 관리자):
  - `주차권` 페이지의 `관리 목록` 상단 탭에서 조회
  - 부서/팀/검색/날짜 필터
  - 플랫폼 관리자가 아니면 본인 소속 부서 범위 내에서만 검색

`parking_admin` 역할도 `seed_org_chart` 실행 시 자동 생성됩니다.

## 5-3) 계정관리 탭 구조

- 좌측 메뉴는 `계정관리` 단일 탭으로 노출
- 페이지 내부 상단 탭:
  - `계정 직책`: `/accounts/manage/roles/`
  - `가입 승인`: `/accounts/manage/approvals/`
- `계정 직책`의 직책 목록은 API(`/api/v1/users/roles/assignable/`)로 로딩
- `가입 승인`에서는 승인 전 신청 부서/팀을 수정한 뒤 승인/반려 처리 가능

## 6) Docker Compose + Nginx + HTTPS

저장소 루트 기준으로 아래 파일을 추가했습니다.

- `docker-compose.prod.yml`
- `.deploy/nginx/nginx.conf`
- `.deploy/nginx/conf.d/jcc-seoul.conf`
- `.deploy/ddns-route53.yml`
- `.deploy/env/nginx-certbot.env.example`

사전 준비:

1. DNS에 아래 A/CNAME 등록
   - `shalom.jcc-seoul.com`
   - `shalom.admin.jcc-seoul.com`
   - `shalom.api.jcc-seoul.com`
   - `shalom.docs.jcc-seoul.com`
2. `.deploy/env/nginx-certbot.env.example`를 복사해 `.deploy/env/nginx-certbot.env` 생성
3. 루트 `.env`에 도메인/보안 관련 값 확인

Nginx 이미지는 `jonasal/nginx-certbot:latest`를 사용합니다.
(`dns-route53` 인증 방식, env 파일 기반)

권장 환경 변수:

```bash
SUBDOMAIN_ROUTING_ENABLED=true
APP_HOST=shalom.jcc-seoul.com
ADMIN_HOST=shalom.admin.jcc-seoul.com
API_HOST=shalom.api.jcc-seoul.com
DOCS_HOST=shalom.docs.jcc-seoul.com
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
KAKAO_REDIRECT_URI=https://shalom.jcc-seoul.com/auth/complete/kakao/
```

인증서 발급 방식:

```bash
cp .deploy/env/nginx-certbot.env.example .deploy/env/nginx-certbot.env
# .deploy/env/nginx-certbot.env 에 실제 AWS 키 입력
```

서비스 기동:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

주의:

- 현재 `docker-compose.prod.yml`은 질문에서 주신 포맷을 기반으로 구성되어 있습니다.
- `redis`/`rabbitmq` IP 충돌(`172.19.0.8`)은 `rabbitmq`를 `172.19.0.9`로 조정했습니다.

