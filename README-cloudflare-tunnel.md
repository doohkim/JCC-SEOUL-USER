# Cloudflare Tunnel 운영 가이드 (Docker Compose)

대상: `jcc-seoul.com` (Cloudflare NS 전환 완료), tunnel 이름 `jcc-seoul-user`  
방식: **remotely managed tunnel + token**

이 문서는 기존 `Route53 DDNS + 공유기 포트포워딩`에서 Cloudflare Tunnel로 전환하는 실무 절차입니다.

## 1) 현재 방식 vs Tunnel 방식

### 기존 방식
- 공인 IP 변경 시 Route53 DDNS로 DNS 갱신
- 공유기 80/443 포트포워딩 필요
- 외부 인바운드가 서버로 직접 유입

### Cloudflare Tunnel 방식
- 서버에서 Cloudflare로 **아웃바운드 연결**만 유지
- **공유기 80/443 포트포워딩 불필요**
- 공인 IP 추적/DDNS 필요성이 크게 줄어듦

## 2) 왜 `shalom.*` A 레코드를 수동으로 만들면 안 되나

- Tunnel 라우팅은 Cloudflare Zero Trust의 **Public Hostname**이 진짜 소스 오브 트루스입니다.
- `shalom.*`를 A 레코드로 서버 공인 IP에 직접 연결하면 Tunnel을 우회해 기존 인바운드 경로가 열립니다.
- 결과적으로 보안/운영 모델이 섞여 장애 분석이 어려워지고, 포트포워딩 제거 효과도 사라집니다.

정리: `shalom.jcc-seoul.com`, `shalom.api.jcc-seoul.com`, `shalom.admin.jcc-seoul.com`, `shalom.docs.jcc-seoul.com`는 **Dashboard의 Tunnel Public Hostname으로 관리**하세요.

---

## 3) Compose 구성

`docker-compose.prod.yml`의 `cloudflared` 서비스:

- 이미지: `cloudflare/cloudflared:2024.11.0` (고정 태그 권장, `latest` 미사용)
- 실행: `tunnel --no-autoupdate run --token ${CLOUDFLARE_TUNNEL_TOKEN}`
- 포트 publish 없음
- 재시작 정책: `restart: unless-stopped`
- 로그 로테이션 포함

`depends_on`은 넣지 않았습니다. cloudflared는 터널 세션 유지가 핵심이라, 백엔드 지연 기동 시에도 자체 재연결로 운영 가능합니다.

---

## 4) `.env` 설정

```dotenv
CLOUDFLARE_TUNNEL_TOKEN=replace_with_cloudflare_tunnel_token
CLOUDFLARED_IMAGE=cloudflare/cloudflared:2024.11.0
```

- Tunnel token은 절대 Git에 커밋하지 마세요.
- CI/CD secret 또는 서버 로컬 `.env`로만 관리하세요.

---

## 5) 1회성 테스트 (`docker run`)

Compose 적용 전에 토큰 유효성만 빠르게 검증할 때:

```bash
docker run --rm \
  cloudflare/cloudflared:2024.11.0 \
  tunnel --no-autoupdate run --token "$CLOUDFLARE_TUNNEL_TOKEN"
```

정상 시 `Registered tunnel connection` 로그가 출력됩니다.

---

## 6) Cloudflare Dashboard route 설정 절차

1. Zero Trust > Networks > Tunnels > `jcc-seoul-user` 선택
2. Public Hostname 추가
3. 1차 검증 라우트 먼저 추가
   - Hostname: `shalom.jcc-seoul.com`
   - Service: `http://nginx:80`
4. 검증 완료 후 확장 라우트 추가
   - `shalom.api.jcc-seoul.com` -> `http://api:8000`
   - `shalom.admin.jcc-seoul.com` -> `http://admin:3000`
   - `shalom.docs.jcc-seoul.com` -> `http://docs:3000`

---

## 7) 실행 및 활성화 확인 절차

```bash
docker compose -f docker-compose.prod.yml --profile production up -d cloudflared
docker logs -f cloudflared
```

활성화 판단 기준:
- 로그에 `Registered tunnel connection` 1개 이상
- Dashboard에서 tunnel 상태가 `Healthy/Active`
- 외부망에서 `https://shalom.jcc-seoul.com` 접속 성공

### Tunnel이 Inactive일 때 확인
- token 오탈자/만료 여부
- Tunnel 이름 혼동(토큰 발급 대상 tunnel 확인)
- 서버 아웃바운드 인터넷 가능 여부(443 차단 여부)
- 컨테이너 실행 여부: `docker ps | rg cloudflared`
- 로그 에러: `docker logs --tail 200 cloudflared`

---

## 8) Route53 DDNS 중지 / 포트포워딩 제거 시점

순서가 중요합니다.

1. `shalom.jcc-seoul.com` Tunnel 경유 검증 완료
2. cloudflared 안정 운영 확인(최소 수시간 모니터링 권장)
3. Route53 DDNS 컨테이너 중지
4. 공유기 80/443 포트포워딩 제거

즉, **Tunnel 정상 동작 확인 후** 제거합니다.

---

## 9) 체크리스트

- [ ] Cloudflare NS 전환 확인 (`jcc-seoul.com`)
- [ ] Tunnel `jcc-seoul-user` 생성 및 token 발급
- [ ] `.env`에 `CLOUDFLARE_TUNNEL_TOKEN` 설정
- [ ] `docker compose up -d cloudflared` 실행
- [ ] `docker logs -f cloudflared`에서 `Registered tunnel connection` 확인
- [ ] Dashboard Public Hostname: `shalom.jcc-seoul.com -> http://nginx:80`
- [ ] 외부망 접속 검증
- [ ] Route53 DDNS 중지
- [ ] 포트포워딩 제거
- [ ] 이후 `shalom.api/admin/docs` 순차 확장

---

## 10) 트러블슈팅

### A. `Cannot connect to the Docker daemon`
- Docker Desktop/daemon 미기동
- `docker info`에서 `Server` 섹션 확인

### B. `env file ... nginx-certbot.env not found`
- compose 파싱 시 nginx `env_file`이 없어도 실패할 수 있음
- 빈 파일 생성:
  - `mkdir -p .deploy/env && touch .deploy/env/nginx-certbot.env`

### C. 컨테이너는 Running인데 Tunnel Inactive
- token 불일치/만료 확인
- Dashboard에서 해당 tunnel에 public hostname 연결 여부 확인
- 로그의 `Unauthorized`/`token` 관련 메시지 점검

### D. 도메인 접속 불가
- Public Hostname의 Service URL이 실제 내부 컨테이너명/포트와 일치하는지 확인
- backend 컨테이너 health 확인
- Cloudflare DNS에 동일 호스트 A/CNAME 수동 레코드가 충돌하는지 확인

---

## 11) 롤백 절차

1. cloudflared 중지
```bash
docker compose -f docker-compose.prod.yml --profile production stop cloudflared
```
2. 기존 포트포워딩(80/443) 복구
3. Route53 DDNS 재가동
```bash
docker compose -f docker-compose.prod.yml --profile production up -d ddns-route53
```
4. 외부 접속 정상 확인
