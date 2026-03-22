# 로컬 초기 데이터 (admin + 엑셀 + 출석)

## 한 번에 실행

1. 엑셀: 저장소 **`app/fixtures/2026 예배 출석 명단.xlsx`** 가 이미 있으면 추가 작업 없음.  
   없으면 `~/Downloads/` 에 두거나 `--xlsx` / `JCC_SEED_XLSX` 로 경로 지정.

2. 프로젝트 앱 디렉터리에서:

```bash
cd app
python manage.py migrate
python manage.py bootstrap_dev
```

- **admin / 1234** 슈퍼유저 생성(또는 비밀번호 재설정)
- 조직도(`seed_org_chart`): 부서·직급·직책·일하는 부서
- 엑셀 **「주일 88」** 시트 → 청년부 팀·**교적 Member**·소속
- **주간 출석 주차** 12주(`AttendanceWeek`)
- 같은 파일에서 **「26.xx.xx 주일예배」** 시트를 자동 탐지해 **주일 출석 행**(`SundayAttendanceLine`) 저장  
  - 자동 선택: 시트명 날짜(`YY.MM.DD`)가 **가장 최근**인 주일예배 시트 1개 (집회·`주일 88` 등은 제외)  
  - 특정 시트만: `python manage.py bootstrap_dev --sunday-sheet "26.03.22 주일예배"`  
  - 엑셀 구조 설명: **`docs/DATA_XLSX.md`**

## 옵션

| 옵션 | 설명 |
|------|------|
| `--xlsx PATH` | 엑셀 경로 |
| `--roster-sheet "주일 88"` | 팀/이름 로스터 시트 (기본 `주일 88`) |
| `--sunday-sheet "26.03.22 주일예배"` | 주일 참석 명단 시트 (미지정 시 자동 탐지) |
| `--skip-excel` | 엑셀 없이 admin + 조직 + 주차만 |
| `--skip-sunday` | 로스터·주차는 하되 주일 출석 라인만 스킵 |
| `--weeks N` | 주차 개수 (기본 12) |

## 개별 커맨드 (참고)

```bash
python manage.py bootstrap_admin          # admin / 1234
python manage.py seed_org_chart
python manage.py seed_youth_roster [엑셀경로] --sheet "주일 88"
python manage.py ensure_weekly_attendance_weeks --weeks 12 --division-code youth
python manage.py import_sunday_attendance_xlsx 엑셀경로 --sheet "26.03.22 주일예배"
```

의존성: **openpyxl** (`pyproject.toml`에 포함)
