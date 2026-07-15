#!/usr/bin/env bash
set -euo pipefail

# 현재 docker postgres 컨테이너의 DB를 custom dump(-Fc)로 백업한다.
#
# Usage:
#   scripts/local_docker_db_backup.sh [output_file]
#
# Optional env:
#   LOCAL_PG_CONTAINER (default: postgres-django)
#   LOCAL_DB_USER      (default: jccseoul)
#   LOCAL_DB_NAME      (default: jccseoul)

LOCAL_PG_CONTAINER="${LOCAL_PG_CONTAINER:-postgres-django}"
LOCAL_DB_USER="${LOCAL_DB_USER:-jccseoul}"
LOCAL_DB_NAME="${LOCAL_DB_NAME:-jccseoul}"

DEFAULT_OUTPUT="$HOME/${LOCAL_DB_NAME}_$(date +%Y%m%d_%H%M%S).dump"
OUTPUT_PATH="${1:-$DEFAULT_OUTPUT}"

if ! docker ps --format '{{.Names}}' | rg -x "${LOCAL_PG_CONTAINER}" >/dev/null; then
  echo "[ERROR] 실행 중인 컨테이너를 찾을 수 없습니다: ${LOCAL_PG_CONTAINER}" >&2
  exit 1
fi

docker exec -i "${LOCAL_PG_CONTAINER}" pg_dump \
  -U "${LOCAL_DB_USER}" \
  -d "${LOCAL_DB_NAME}" \
  -Fc \
  --no-owner \
  --no-acl \
  > "${OUTPUT_PATH}"

echo "[OK] backup saved: ${OUTPUT_PATH}"
