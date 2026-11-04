#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
"$ROOT/deploy/check_secret_permissions.sh"
"${COMPOSE[@]}" up -d --wait postgres redis
"${COMPOSE[@]}" build backend frontend market-worker execution-worker portfolio-worker dhan-stream-worker
"$ROOT/deploy/backup_database.sh"
"$ROOT/deploy/provision_database_role.sh"
"$ROOT/deploy/migrate_database.sh"
"${COMPOSE[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 180 \
  backend frontend market-worker execution-worker portfolio-worker dhan-stream-worker
# Recreate upstream resolution after backend/frontend container addresses change.
# No Nginx configuration file or public-domain setting is changed.
"${COMPOSE[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 60 nginx
"$ROOT/deploy/validate_environment.sh"
GNK_ENV=production "$ROOT/deploy/gnk-service.sh" health
"${COMPOSE[@]}" exec -T backend python -c \
  'from importlib.metadata import version; assert version("dhanhq")=="2.3.0"; print("DhanHQ SDK 2.3.0 installed.")'
printf '\nOpen /user/dhan and /user/portfolio, then verify your own Dhan account reads.\n'
