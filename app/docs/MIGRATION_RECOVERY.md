# 마이그레이션 재생성 후 DB 복구

앱 분리(`users` / `registry` / `attendance`) 이후 **테이블 이름은 그대로** `users_*` 를 쓰므로, DB 안의 데이터는 유지됩니다. 바뀌는 것은 **django_migrations 기록**과 **코드상 마이그레이션 파일**뿐입니다.

## `Dependency on app with no migrations: users`

다른 PC에서 클론했는데 **`users/migrations/0001_initial.py`**(및 `registry`·`attendance` 동일)가 없으면 위 오류가 납니다.  
**마이그레이션 `.py` 파일은 반드시 Git에 포함**되어 있어야 합니다(`.gitignore`로 `migrations/` 전체를 빼지 마세요).

```bash
git pull
ls users/migrations/0001_initial.py registry/migrations/0001_initial.py attendance/migrations/0001_initial.py
python manage.py migrate
```

## Admin 404: `/admin/users/attendanceweek/...`

교적·출석 모델은 `registry` / `attendance` 앱으로 옮겼습니다. 옛 주소는 자동으로 새 Admin으로 **리다이렉트**됩니다  
(`config/admin_legacy_redirect.py`).

## 1) 빈 DB (처음부터)

```bash
cd app
python manage.py migrate
```

## 2) 이미 `users_*` 테이블이 있는 기존 DB (데이터 유지)

**반드시 먼저 DB 백업** (dump / 스냅샷).

### A. 마이그레이션 이력만 갈아엎는 경우

이전에 적용돼 있던 `users` / `registry` / `attendance` 마이그레이션 이름이 현재 파일과 맞지 않으면, 아래로 정리한 뒤 다시 맞춥니다.

**SQLite 예시**

```bash
sqlite3 db.sqlite3 "DELETE FROM django_migrations WHERE app IN ('users','registry','attendance');"
```

**PostgreSQL 예시**

```sql
DELETE FROM django_migrations WHERE app IN ('users', 'registry', 'attendance');
```

그 다음:

```bash
python manage.py migrate --fake-initial
```

- 각 앱의 **초기(initial) 마이그레이션**에 해당하는 테이블이 이미 있으면, 그 마이그레이션만 **적용한 것으로 표기(FAKE)** 하고 실제 DDL은 실행하지 않습니다.
- 현재 구조는 앱당 **하나의 초기 마이그레이션**(`0001_initial`)만 두었기 때문에 `--fake-initial` 한 번으로 맞추기 쉽습니다.

적용 순서는 의존성에 따라 자동으로 됩니다: `users` → `registry` → `attendance`.

### B. `--fake-initial` 이 안 먹는 경우

- `django_migrations`에 일부만 남아 있거나, 테이블은 있는데 앱 이름이 다른 경우 등.

수동으로 맞출 때:

```bash
python manage.py migrate users --fake-initial
python manage.py migrate registry --fake-initial
python manage.py migrate attendance --fake-initial
```

여전히 어긋나면 백업 후 `django_migrations`에서 해당 앱 행을 지우고 위를 다시 시도하세요.

## 3) 확인

```bash
python manage.py showmigrations users registry attendance
python manage.py check
```

## 4) 현재 마이그레이션 파일

| 앱          | 파일                         |
|------------|------------------------------|
| `users`    | `users/migrations/0001_initial.py` |
| `registry` | `registry/migrations/0001_initial.py` (squash 1개) |
| `attendance` | `attendance/migrations/0001_initial.py` (squash 1개) |

모델의 `Meta.db_table` 으로 기존 `users_*` 물리 테이블에 매핑됩니다.
