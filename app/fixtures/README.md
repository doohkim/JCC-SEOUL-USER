# 초기 데이터용 엑셀

`2026 예배 출석 명단.xlsx` 를 이 폴더에 두면, `Downloads` 에 파일이 없어도 `bootstrap_dev` 가 자동으로 찾습니다.

```bash
cd app
python manage.py bootstrap_dev
```

우선순위: `--xlsx` → 환경변수 `JCC_SEED_XLSX` → **`app/fixtures/`** → `~/Downloads/`
