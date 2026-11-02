#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
command -v gpg >/dev/null || { echo 'Install gpg for encrypted backups' >&2; exit 1; }
[[ -n "${GNK_BACKUP_RECIPIENT:-}" ]] || { echo 'Set GNK_BACKUP_RECIPIENT to the backup encryption public-key fingerprint' >&2; exit 1; }
umask 077
mkdir -p "$ROOT/backups"
target="$ROOT/backups/gnk-$(date -u +%Y%m%dT%H%M%SZ)-${RANDOM}.dump.gpg"
[[ ! -e "$target" ]] || { echo 'Backup path already exists' >&2; exit 1; }
trap 'rm -f -- "$target.partial"' EXIT
"${COMPOSE[@]}" exec -T postgres pg_dump -U gnk -d gnk --format=custom |
  gpg --batch --yes --encrypt --recipient "$GNK_BACKUP_RECIPIENT" --output "$target.partial"
mv -- "$target.partial" "$target"
sha256sum "$target" > "$target.sha256"
printf 'Encrypted backup created: %s\n' "$target"
