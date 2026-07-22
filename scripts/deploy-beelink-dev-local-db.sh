#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

docker compose --env-file ./.deploy/dev/env -f docker-compose.dev.yml up --build --force-recreate --remove-orphans -d
