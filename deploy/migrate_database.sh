#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
# The backend and migrator have separate image tags. Always rebuild the migrator
# so a previous deployment cannot silently reuse an image missing new revisions.
"${COMPOSE[@]}" -f "$ROOT/docker-compose.migrate.yml" build migrator
"${COMPOSE[@]}" -f "$ROOT/docker-compose.migrate.yml" run --rm --no-deps migrator

# Verify the committed schema in a fresh connection; a successful command alone
# must not be mistaken for an applied migration or a matching image revision.
"${COMPOSE[@]}" -f "$ROOT/docker-compose.migrate.yml" run --rm --no-deps -T --entrypoint python migrator - <<'PYVERIFY'
from app import main
from app.database.session import engine
from app.database.readiness import check_schema
with engine.connect() as connection:
    check_schema(connection)
print('Migration schema verification passed.')
PYVERIFY
