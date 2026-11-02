#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
exec "${COMPOSE[@]}" run --rm --no-deps backend python /app/infrastructure/env/validation.py --connectivity
