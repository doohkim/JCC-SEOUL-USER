#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

docker compose --env-file ./.deploy/prod_onprem/env -f docker-compose.prod.onprem.rds.yml up --build --force-recreate --remove-orphans -d
