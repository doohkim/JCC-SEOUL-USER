#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  JCC_SEOUL_RDS_HOST=... JCC_SEOUL_RDS_PORT=... JCC_SEOUL_RDS_USER=... \
  JCC_SEOUL_RDS_DB=... JCC_SEOUL_RDS_PASSWORD=... \
    scripts/restore_rds_backup.sh [dump-file]

  or:

  RDS_HOST=... RDS_PORT=... RDS_USER=... RDS_DB=... RDS_PASSWORD=... \
    scripts/restore_rds_backup.sh [dump-file]

Defaults:
  dump-file: jccseoul.dump

Safety:
  This runs pg_restore with --clean --if-exists against the target database.
  Type the target DB name when prompted, or set RESTORE_CONFIRM=<RDS_DB>.

Optional:
  PG_RESTORE_BIN=/path/to/pg_restore
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

RDS_HOST="${RDS_HOST:-${JCC_SEOUL_RDS_HOST:-}}"
RDS_PORT="${RDS_PORT:-${JCC_SEOUL_RDS_PORT:-}}"
RDS_USER="${RDS_USER:-${JCC_SEOUL_RDS_USER:-}}"
RDS_DB="${RDS_DB:-${JCC_SEOUL_RDS_DB:-}}"
RDS_PASSWORD="${RDS_PASSWORD:-${JCC_SEOUL_RDS_PASSWORD:-}}"

required_vars=(RDS_HOST RDS_PORT RDS_USER RDS_DB RDS_PASSWORD)
for var_name in "${required_vars[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    echo "Missing required environment variable: ${var_name}" >&2
    echo "If you set JCC_SEOUL_RDS_* in ~/.zshrc, make sure each line starts with export." >&2
    usage >&2
    exit 2
  fi
done

dump_file="${1:-jccseoul.dump}"
if [[ ! -f "$dump_file" ]]; then
  echo "Dump file not found: $dump_file" >&2
  exit 2
fi

pg_restore_bin="${PG_RESTORE_BIN:-}"
if [[ -z "$pg_restore_bin" ]]; then
  if command -v pg_restore >/dev/null 2>&1; then
    pg_restore_bin="$(command -v pg_restore)"
  elif [[ -x /opt/homebrew/opt/postgresql@18/bin/pg_restore ]]; then
    pg_restore_bin="/opt/homebrew/opt/postgresql@18/bin/pg_restore"
  elif [[ -x /opt/homebrew/opt/postgresql@17/bin/pg_restore ]]; then
    pg_restore_bin="/opt/homebrew/opt/postgresql@17/bin/pg_restore"
  elif [[ -x /opt/homebrew/opt/postgresql@16/bin/pg_restore ]]; then
    pg_restore_bin="/opt/homebrew/opt/postgresql@16/bin/pg_restore"
  fi
fi

if [[ -z "$pg_restore_bin" || ! -x "$pg_restore_bin" ]]; then
  echo "pg_restore not found. Install PostgreSQL client tools first, or set PG_RESTORE_BIN." >&2
  exit 127
fi

echo "Target: ${RDS_USER}@${RDS_HOST}:${RDS_PORT}/${RDS_DB}"
echo "Dump:   ${dump_file}"
echo "Tool:   ${pg_restore_bin}"
echo
echo "WARNING: this will restore with --clean --if-exists and may drop existing objects."

confirm="${RESTORE_CONFIRM:-}"
if [[ -z "$confirm" ]]; then
  read -r -p "Type '${RDS_DB}' to continue: " confirm
fi

if [[ "$confirm" != "$RDS_DB" ]]; then
  echo "Confirmation did not match. Aborted." >&2
  exit 1
fi

export PGPASSWORD="$RDS_PASSWORD"
trap 'unset PGPASSWORD' EXIT

"$pg_restore_bin" \
  -h "$RDS_HOST" -p "$RDS_PORT" -U "$RDS_USER" -d "$RDS_DB" \
  --clean --if-exists --no-owner --no-privileges -j 4 \
  "$dump_file"
