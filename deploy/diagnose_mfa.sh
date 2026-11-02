#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
if command -v timedatectl >/dev/null; then
  timedatectl show -p NTPSynchronized -p NTP -p Timezone || true
fi
GNK_MFA_EMAIL="${1:-}"
if [[ -z "$GNK_MFA_EMAIL" ]]; then
  read -r -p 'Account email (local diagnosis only; never enter an MFA code): ' GNK_MFA_EMAIL
fi
[[ -n "$GNK_MFA_EMAIL" ]] || { printf 'Account email required.\n' >&2; exit 1; }
"${COMPOSE[@]}" run --rm --no-deps -e "GNK_MFA_EMAIL=$GNK_MFA_EMAIL" backend python /app/infrastructure/env/mfa_diagnostics.py
