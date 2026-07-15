#!/usr/bin/env bash
set -euo pipefail

# RDS PostgreSQL 데이터베이스를 생성한다.
#
# Required env:
#   RDS_HOST, RDS_PORT, RDS_DB, RDS_USER
# Optional env:
#   RDS_PASSWORD       (없으면 프롬프트 입력)
#   RDS_OWNER          (default: RDS_USER)
#   RDS_MAINTENANCE_DB (default: postgres)

: "${RDS_HOST:?RDS_HOST is required}"
: "${RDS_PORT:?RDS_PORT is required}"
: "${RDS_DB:?RDS_DB is required}"
: "${RDS_USER:?RDS_USER is required}"

RDS_OWNER="${RDS_OWNER:-${RDS_USER}}"
RDS_MAINTENANCE_DB="${RDS_MAINTENANCE_DB:-postgres}"

if [[ -z "${RDS_PASSWORD:-}" ]]; then
  read -r -s -p "RDS_PASSWORD: " RDS_PASSWORD
  echo
fi

PGPASSWORD="${RDS_PASSWORD}" psql \
  "host=${RDS_HOST} port=${RDS_PORT} dbname=${RDS_MAINTENANCE_DB} user=${RDS_USER} sslmode=require" \
  -v ON_ERROR_STOP=1 \
  -v db_name="${RDS_DB}" \
  -v db_owner="${RDS_OWNER}" <<'SQL'
SELECT format(
  'CREATE DATABASE %I OWNER %I TEMPLATE template0 ENCODING ''UTF8''',
  :'db_name',
  :'db_owner'
) \gexec
SQL

echo "[OK] created database: ${RDS_DB} (owner=${RDS_OWNER})"
