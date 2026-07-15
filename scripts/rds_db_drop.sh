#!/usr/bin/env bash
set -euo pipefail

# RDS PostgreSQL 데이터베이스를 drop 한다.
#
# Required env:
#   RDS_HOST, RDS_PORT, RDS_DB, RDS_USER
# Optional env:
#   RDS_PASSWORD       (없으면 프롬프트 입력)
#   RDS_MAINTENANCE_DB (default: postgres)

: "${RDS_HOST:?RDS_HOST is required}"
: "${RDS_PORT:?RDS_PORT is required}"
: "${RDS_DB:?RDS_DB is required}"
: "${RDS_USER:?RDS_USER is required}"

RDS_MAINTENANCE_DB="${RDS_MAINTENANCE_DB:-postgres}"

if [[ -z "${RDS_PASSWORD:-}" ]]; then
  read -r -s -p "RDS_PASSWORD: " RDS_PASSWORD
  echo
fi

echo "[WARN] DROP DATABASE target: ${RDS_HOST}:${RDS_PORT}/${RDS_DB}"
read -r -p "계속하려면 DB 이름(${RDS_DB})을 그대로 입력: " CONFIRM_DB
if [[ "${CONFIRM_DB}" != "${RDS_DB}" ]]; then
  echo "[ABORT] 확인값이 일치하지 않아 중단했습니다."
  exit 1
fi

PGPASSWORD="${RDS_PASSWORD}" psql \
  "host=${RDS_HOST} port=${RDS_PORT} dbname=${RDS_MAINTENANCE_DB} user=${RDS_USER} sslmode=require" \
  -v ON_ERROR_STOP=1 \
  -v db_name="${RDS_DB}" <<'SQL'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = :'db_name'
  AND pid <> pg_backend_pid();

SELECT format('DROP DATABASE IF EXISTS %I', :'db_name') \gexec
SQL

echo "[OK] dropped database: ${RDS_DB}"
