#!/usr/bin/env bash
# Read-only activation diagnostics; never edits flags, approvals or accounts.
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
broker="${1:-dhan}"
case "$broker" in dhan|upstox) ;; *) printf 'Use dhan or upstox.\n' >&2; exit 2 ;; esac
"${COMPOSE[@]}" exec -T backend python - "$broker" <<'PY'
import sys
from sqlalchemy import select
from app.database.session import DB
from app.database.tenancy import set_context
from app.models.identity import User
from app.execution.readiness import snapshot
broker=sys.argv[1]
with DB() as s:
    users=list(s.scalars(select(User.id).where(User.active.is_(True),User.verified.is_(True))))
count=0
for uid in users:
    with DB() as s:
        set_context(s,uid)
        data=snapshot(s,uid,broker)
        if not data['accounts']:continue
        for account in data['accounts']:
            count+=1
            print(f'{broker.upper()} account {count}: '+('PLACEMENT ENABLED' if account['placement_ready'] else 'PLACEMENT LOCKED'))
            for item in account['blockers']:
                print('  '+item['code']+': '+item['action'])
if not count:print('No connected-account records found for '+broker+'. Connect your owned broker account in GNK.')
print('No flags, approvals, account arming, or orders were changed. Per-order checks still apply.')
PY
