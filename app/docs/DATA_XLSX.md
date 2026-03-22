# 예배 출석 엑셀 (`2026 예배 출석 명단.xlsx`)

교회에서 쓰는 **예배 참석·명단** 통합 워크북입니다.

**저장소에 포함:** `app/fixtures/2026 예배 출석 명단.xlsx` — `bootstrap_dev` 가 `Downloads` 에 없을 때 자동 사용합니다.

탐색 순서: `--xlsx` → 환경변수 `JCC_SEED_XLSX` → **`app/fixtures/`** → `~/Downloads/`

## 시트 역할 (실제 파일 기준)

| 시트 예시 | 용도 |
|-----------|------|
| **주일 88** | 청년부 팀별 이름 로스터 → `seed_youth_roster` (교적 Member·팀 소속) |
| **26.03.22 주일예배** | 주일 참석자 명단(팀 블록·현장·인천 열) → `import_sunday_attendance_xlsx` → `SundayAttendanceLine` |
| **26.03.25 수요예배**, **26.03.28 토요예배** | 수·토 시트는 현재 **자동 임포트 대상 아님** (주간 출석 API/Admin에서 수동 입력 또는 추후 전용 임포트) |
| **주일 인천** | 로스터 성격 — `주일 88`과 별도. 필요 시 시트명에 맞춰 별도 파이프라인 검토 |
| **이시대 목사님 집회…** | 집회 명단 — `bootstrap_dev` 자동 주일 시트 후보에서 제외 |

## 한 번에 넣기

```bash
cd app
python manage.py bootstrap_dev
```

- **주일 88** → 교적·팀  
- **주일예배** 시트는 시트명의 **날짜가 가장 최근**인 것 하나를 골라 주일 출석 행으로 임포트합니다.  
- 특정 주만 넣으려면:

```bash
python manage.py bootstrap_dev --sunday-sheet "26.03.22 주일예배"
```

## 주일만 따로

```bash
python manage.py import_sunday_attendance_xlsx \
  "$HOME/Downloads/2026 예배 출석 명단.xlsx" \
  --sheet "26.03.22 주일예배"
```

## 형식 참고

- **주일 88**: `부서 회장단` 행 + 팀 열 헤더 + 이름 셀 (기존 `youth_roster_xlsx` 파서).
- **주일예배 시트**: 상단 제목에 `YYYY.MM.DD 주일예배 참석자 명단` 형태 날짜, 팀별 (이름|현장|인천) 블록 (`sunday_attendance_xlsx` 파서).
