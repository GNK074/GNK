#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
"${COMPOSE[@]}" -f "$ROOT/docker-compose.migrate.yml" run --rm --no-deps migrator
