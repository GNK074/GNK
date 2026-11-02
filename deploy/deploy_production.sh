#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# Existing production database must already be running and backed up.
GNK_ENV=production "$ROOT/deploy/gnk-service.sh" build
"$ROOT/deploy/backup_database.sh"
"$ROOT/deploy/provision_database_role.sh"
"$ROOT/deploy/migrate_database.sh"
GNK_ENV=production "$ROOT/deploy/gnk-service.sh" deploy
"$ROOT/deploy/validate_environment.sh"
