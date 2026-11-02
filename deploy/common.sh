#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose --project-directory "$ROOT" --env-file "$ROOT/.env" -f "$ROOT/docker-compose.yml" -f "$ROOT/docker-compose.prod.yml")
command -v docker >/dev/null || { echo 'Docker required' >&2; exit 1; }
[[ -f "$ROOT/.env" ]] || { echo 'Configure .env first' >&2; exit 1; }
