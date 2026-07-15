#!/usr/bin/env bash
set -euo pipefail

# RDS PostgreSQL 데이터베이스로 backup dump를 복원한다.
#
# Usage:
#   scripts/rds_db_restore.sh <dump_file>
#
# Required env:
#   RDS_HOST, RDS_PORT, RDS_DB, RDS_USER
# Optional env:
#   RDS_PASSWORD (없으면 프롬프트 입력)

DUMP_FILE="${1:-}"
if [[ -z "${DUMP_FILE}" ]]; then
  echo "usage: scripts/rds_db_restore.sh <dump_file>" >&2
  exit 1
fi

if [[ ! -f "${DUMP_FILE}" ]]; then
  echo "[ERROR] dump 파일을 찾을 수 없습니다: ${DUMP_FILE}" >&2
  exit 1
fi

: "${RDS_HOST:?RDS_HOST is required}"
: "${RDS_PORT:?RDS_PORT is required}"
: "${RDS_DB:?RDS_DB is required}"
: "${RDS_USER:?RDS_USER is required}"

if [[ -z "${RDS_PASSWORD:-}" ]]; then
  read -r -s -p "RDS_PASSWORD: " RDS_PASSWORD
  echo
fi

echo "[INFO] restore target: ${RDS_HOST}:${RDS_PORT}/${RDS_DB}"

PGPASSWORD="${RDS_PASSWORD}" pg_restore \
  -h "${RDS_HOST}" \
  -p "${RDS_PORT}" \
  -U "${RDS_USER}" \
  -d "${RDS_DB}" \
  --no-owner \
  --no-acl \
  --verbose \
  --exit-on-error \
  "${DUMP_FILE}"

echo "[OK] restore completed: ${DUMP_FILE}"
