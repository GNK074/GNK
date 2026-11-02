#!/usr/bin/env bash
# Read-only diagnosis for the existing Oracle installation; no source update needed.
set -Eeuo pipefail
cd /opt/gnk
if command -v timedatectl >/dev/null; then
  timedatectl show -p NTPSynchronized -p NTP -p Timezone || true
fi
read -r -p 'Login email (local only; do not enter an MFA code): ' GNK_MFA_EMAIL
[[ -n "$GNK_MFA_EMAIL" ]] || { printf 'Login email required.\n' >&2; exit 1; }
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm --no-deps -T -e "GNK_MFA_EMAIL=$GNK_MFA_EMAIL" --entrypoint python backend - <<'PY'
import os, time, json, base64
from datetime import datetime, timezone
from sqlalchemy import select
from app.database.session import DB
from app.models.identity import User
from app.security.encryption import decrypt
try:
    stamp=time.time()
    result={'server_utc':datetime.fromtimestamp(stamp,timezone.utc).isoformat()}
    with DB() as s:
        row=s.execute(select(User.mfa_enabled,User.mfa_counter,User.mfa_secret).where(User.email==os.environ['GNK_MFA_EMAIL'].strip().lower())).first()
    result['account_found']=row is not None
    if row:
        enabled,counter,encrypted=row
        readable=False
        try:
            secret=decrypt(encrypted) if encrypted else ''
            readable=len(base64.b32decode(secret+'='*((8-len(secret)%8)%8)))>=16
        except Exception:
            pass
        result.update(mfa_enabled=enabled,setup_key_present=bool(encrypted),setup_key_readable=readable,counter_ahead_of_acceptance_window=counter>int(stamp//30)+1,seconds_until_unused_time_step=max(0,(counter+1)*30-int(stamp)) if counter>=0 else 0)
    print(json.dumps(result,indent=2))
except Exception:
    print('Inspection failed; database/configuration details suppressed.')
    raise SystemExit(1)
PY
unset GNK_MFA_EMAIL
