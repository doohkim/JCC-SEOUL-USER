# Nginx gzip 압축

## 적용 목적

브라우저가 받는 HTML, JSON, CSS, JavaScript는 반복되는 문자열이 많아 gzip
압축률이 높다. 수련회 전체 명단의 기존 HTML은 로컬 데이터 기준 약 5.2MB였고,
gzip 레벨 6로 압축했을 때 약 109KB까지 줄었다.

gzip은 네트워크 전송량을 줄이지만 브라우저가 생성해야 하는 DOM 개수는 줄이지
않는다. 따라서 전체 명단은 gzip과 별도로 API 서버 페이지네이션을 적용해 한
페이지당 20개 행만 전송한다.

## 요청과 응답 흐름

1. 브라우저가 `Accept-Encoding: gzip, deflate, br` 헤더로 지원 압축 방식을 알린다.
2. Nginx가 응답의 크기와 `Content-Type`을 확인한다.
3. 조건이 맞으면 응답 본문을 gzip으로 압축한다.
4. Nginx가 `Content-Encoding: gzip`을 응답에 추가한다.
5. 브라우저는 본문을 자동으로 해제한 뒤 HTML 또는 JSON으로 처리한다.

애플리케이션 코드는 압축·해제를 직접 처리하지 않는다.

## 적용 설정

```nginx
gzip on;
gzip_comp_level 6;
gzip_min_length 1024;
gzip_vary on;
gzip_proxied any;
gzip_types
    text/plain
    text/css
    text/xml
    application/json
    application/javascript
    application/xml
    application/rss+xml
    image/svg+xml;
```

- `gzip on`: gzip 필터를 활성화한다.
- `gzip_comp_level 6`: 압축률과 CPU 사용량의 균형이 좋은 중간 수준이다.
- `gzip_min_length 1024`: 1KB 미만의 작은 응답은 압축 비용이 더 클 수 있어 제외한다.
- `gzip_vary on`: `Vary: Accept-Encoding`을 추가해 캐시가 압축·비압축 응답을
  구분하도록 한다.
- `gzip_proxied any`: Django/Gunicorn 같은 upstream 프록시 응답도 압축한다.
- `gzip_types`: 기본 압축 대상인 `text/html` 외에 압축할 MIME 타입을 지정한다.

PNG, JPEG, WebP, ZIP, PDF 같은 이미 압축된 형식은 목록에 넣지 않았다. 이런
파일을 다시 gzip으로 압축하면 CPU만 사용하고 크기는 거의 줄지 않는다.

## 배포 반영

설정 파일을 바꾼 것만으로 실행 중인 Nginx가 자동으로 설정을 다시 읽지는 않는다.
배포 환경에서 먼저 문법을 검사한 다음 reload 또는 컨테이너 재시작이 필요하다.

```bash
docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload
```

환경별 compose 파일을 직접 지정해 실행 중이면 동일한 `-f` 옵션을 붙인다.

## 확인 방법

브라우저 개발자 도구의 Network 탭에서 문서 또는 API 응답을 선택하고 다음을
확인한다.

- Request Headers: `Accept-Encoding`에 `gzip` 포함
- Response Headers: `Content-Encoding: gzip`
- Response Headers: `Vary: Accept-Encoding`
- Transferred 크기가 Resource 크기보다 작음

명령행에서는 다음처럼 확인할 수 있다.

```bash
curl -sS -D - -o /dev/null \
  -H 'Accept-Encoding: gzip' \
  https://서비스주소/
```

응답이 1KB 미만이거나 압축 대상 MIME 타입이 아니면 `Content-Encoding`이
나오지 않는 것이 정상이다.

## 주의사항

- gzip은 전송량 최적화이며 DB 조회나 DOM 렌더링 자체를 해결하지 않는다.
- 압축 레벨을 9까지 올려도 크기 감소 폭에 비해 CPU 비용이 크게 늘 수 있다.
- HTTPS 응답의 비밀값과 사용자가 조작 가능한 문자열이 같은 압축 본문에 반복되는
  특수한 구조에서는 BREACH 계열 공격을 검토해야 한다. 일반적으로는 CSRF,
  SameSite 쿠키, 입력 검증을 유지하고 민감한 응답에 사용자 입력을 그대로
  반사하지 않는 것이 중요하다.
