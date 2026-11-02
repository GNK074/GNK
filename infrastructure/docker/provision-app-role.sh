#!/bin/sh
set -eu
password="$(cat /run/secrets/app_db_password)"
case "$password" in *[!A-Za-z0-9_-]*|'') echo 'App DB secret must be URL-safe' >&2; exit 1;; esac
# Do not replace an existing role password. New secret files must match that role.
exists="$(psql -U gnk -d gnk -Atqc "SELECT 1 FROM pg_roles WHERE rolname='gnk_app'")"
if [ "$exists" != 1 ]; then
  printf "CREATE ROLE gnk_app LOGIN PASSWORD '%s' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;\n" "$password" | psql -q -v ON_ERROR_STOP=1 -U gnk -d gnk
fi
unset password
psql -q -v ON_ERROR_STOP=1 -U gnk -d gnk <<'SQL'
ALTER ROLE gnk_app NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;
GRANT CONNECT ON DATABASE gnk TO gnk_app;
GRANT USAGE ON SCHEMA public TO gnk_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO gnk_app;
ALTER DEFAULT PRIVILEGES FOR ROLE gnk IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO gnk_app;
SQL
