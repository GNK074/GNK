#!/bin/sh
set -eu
umask 077
password="$(cat /run/secrets/redis_password)"
case "$password" in *[!A-Za-z0-9_-]*|'') echo 'Redis secret must contain URL-safe characters' >&2; exit 1;; esac
printf 'appendonly yes\nrequirepass %s\n' "$password" > /tmp/gnk-redis.conf
unset password
if [ "$(id -u)" = 0 ]; then
  chown redis:redis /tmp/gnk-redis.conf /data
  exec su-exec redis redis-server /tmp/gnk-redis.conf
fi
exec redis-server /tmp/gnk-redis.conf
