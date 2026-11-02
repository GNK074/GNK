#!/usr/bin/env bash
# Isolated real-container regression: authentication, restart and persistence.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
name="gnk-redis-smoke-$$-${RANDOM}"
tmp="$(mktemp -d)"
cleanup() {
  case "$name" in gnk-redis-smoke-*) docker rm -f "$name" >/dev/null 2>&1 || true; docker volume rm "$name" >/dev/null 2>&1 || true ;; esac
  rm -f -- "$tmp/password"
  rmdir -- "$tmp"
}
trap cleanup EXIT
chmod 755 "$tmp"
printf 'test-only-redis-password_12345\n' > "$tmp/password"
chmod 444 "$tmp/password"
docker volume create "$name" >/dev/null
docker run --detach --name "$name" \
  --mount "type=bind,src=$ROOT/infrastructure/docker/redis-secure.sh,dst=/opt/gnk/redis-secure.sh,readonly" \
  --mount "type=bind,src=$tmp/password,dst=/run/secrets/redis_password,readonly" \
  --mount "type=volume,src=$name,dst=/data" \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m \
  redis:7-alpine sh /opt/gnk/redis-secure.sh >/dev/null
redis_cmd() {
  docker exec "$name" sh -c 'export REDISCLI_AUTH="$(cat /run/secrets/redis_password)"; exec redis-cli "$@"' sh "$@"
}
ready() {
  local attempt
  for attempt in {1..40}; do
    if [[ "$(redis_cmd ping 2>/dev/null || true)" == PONG ]]; then return 0; fi
    sleep 1
  done
  docker logs --tail 30 "$name" >&2
  return 1
}
ready
[[ "$(docker exec "$name" redis-cli ping 2>&1)" == *NOAUTH* ]]
[[ "$(redis_cmd set persistence-check retained)" == OK ]]
docker restart "$name" >/dev/null
ready
[[ "$(redis_cmd get persistence-check)" == retained ]]
printf 'PASS: authenticated Redis boots, restarts and preserves data.\n'
