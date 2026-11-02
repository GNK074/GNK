#!/bin/sh
set -eu
umask 077
password="$(cat /run/secrets/redis_password)"
case "$password" in *[!A-Za-z0-9_-]*|'') echo 'Redis secret must contain URL-safe characters' >&2; exit 1;; esac
# Unique directory avoids overwriting a config owned by a previous Redis process.
runtime_dir="$(mktemp -d /tmp/gnk-redis.XXXXXX)"
trap 'rm -f -- "$runtime_dir/redis.conf"; rmdir -- "$runtime_dir"' EXIT
printf 'appendonly yes\nrequirepass %s\n' "$password" > "$runtime_dir/redis.conf"
unset password
if [ "$(id -u)" = 0 ]; then
  chown redis:redis "$runtime_dir" "$runtime_dir/redis.conf"
fi
# Let the selected official image handle its own privilege-drop implementation
# and /data ownership instead of depending on a particular helper binary.
exec /usr/local/bin/docker-entrypoint.sh redis-server "$runtime_dir/redis.conf"
