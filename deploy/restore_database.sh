#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
[[ $# -eq 1 && -f "$1" ]] || { echo 'Usage: restore_database.sh encrypted.dump.gpg' >&2; exit 1; }
[[ "${GNK_RESTORE_CONFIRM:-}" == RESTORE_STOPPED_DATABASE ]] || { echo 'Stop API/workers first; set GNK_RESTORE_CONFIRM=RESTORE_STOPPED_DATABASE to authorize restoration' >&2; exit 1; }
for service in backend; do
  running="$("${COMPOSE[@]}" ps --status running --quiet "$service")"
  [[ -z "$running" ]] || { echo 'Stop API before restoring' >&2; exit 1; }
done
[[ -f "$1.sha256" ]] || { echo 'Backup checksum manifest required' >&2; exit 1; }
expected="$(cut -d ' ' -f 1 "$1.sha256")"
actual="$(sha256sum "$1" | cut -d ' ' -f 1)"
[[ "$expected" == "$actual" ]] || { echo 'Backup checksum mismatch' >&2; exit 1; }
# Restore refuses to clean/drop a populated database. Use a separately provisioned
# empty database/container and verify restoration before a reviewed cutover.
gpg --decrypt -- "$1" | "${COMPOSE[@]}" exec -T postgres pg_restore -U gnk -d gnk --exit-on-error --single-transaction
