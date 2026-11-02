# Troubleshooting

Environment invalid: validate FIELD_ENCRYPTION_KEY format, independent secret lengths, production HTTPS/MFA/cookies/SMTP flags and secret-file paths. The validator suppresses values deliberately. Do not paste .env or private keys into support tickets.

PostgreSQL connection failure after migration: verify the stored password matches the existing DB role, mounted files are readable inside the appropriate containers, gnk_app exists and grants/default privileges are present. Generating a secret does not change a database password. Production startup rejects superuser/BYPASSRLS API roles.

Redis AUTH failure: coordinate server auth enablement and client secret settings, and recreate Redis only after reviewing persistent data/config. Existing Redis data is retained. Never expose Redis to the public network.

MFA enrollment required: sign in, open /mfa, add the setup key to an authenticator and confirm a fresh code. Codes cannot be replayed; use the next time step after enrollment if signing in again immediately. Keep host time synchronized. Lost-device recovery is an external controlled support process; no bypass endpoint is shipped.

Broker disabled: documentation/application review and auth registry configuration are required. Six requested brokers have no adapter implementation. Upstox has only an auth/profile adapter and is still pending real integration verification. Failed/replayed/expired state requires reconnect. Callback query codes must not be logged. Local disconnect does not guarantee provider-side token revocation.

Paper order rejected: check strategy ownership, stop state, quantity/order value, daily count, daily realized loss and position cap. Short sells are unsupported. Reusing an idempotency key with changed content returns conflict. Unknown price/market data is never fabricated.

Production approval returns 409: inspect missing/expired evidence; even all 18 attestations cannot enable missing execution/reconciliation. Readiness exit 2 is an intentional outstanding production gate, not a crash.

GitHub push from Codex may lack the Git Bash SSH agent. Push from your authenticated Windows Git Bash, then git pull --ff-only on /opt/gnk. A clean matching commit does not imply containers or DNS were deployed.

Mounted secret PermissionError: ordinary Compose file secrets retain host file permissions. On Ubuntu run deploy/check_secret_permissions.sh, then deploy/check_secret_permissions.sh --apply as the operator owning the managed secrets files (or with reviewed administrative access). It validates configured sources and changes only secrets/ to 0700 and its three direct secret files to 0444. It does not read/change password values, recursively chmod directories, or run the API as root. Host directory traversal remains restricted; containers get only their specifically mounted files. External/custom source locations require operator-managed ACLs. After repair, use a one-off backend shell to verify readability, then restart the stack.

## Registration/login fails: column users.gender does not exist

This means the backend image includes the profile fields but the persistent database is still on an older migration. The previous health probe tested connectivity only, so HTTP 200 did not prove schema readiness. Registration and login both select the User model and therefore both fail.

The existing profile migration is `0003`; current releases also require disclosure migration `0004`. Do not remove volumes or stamp the migration version to bypass the upgrade.

The backend and migrator are different Compose services with separate image tags. Building the backend does not refresh an already-built migrator image. `deploy/migrate_database.sh` now builds the migrator before running it, and stops if the build fails. Startup, health and environment validation now check both migration head and actual model columns. Application-side SQL error output also suppresses bound parameter values.

On the VM, take a database backup first using the documented encrypted-backup workflow (`DATABASE_BACKUP_RESTORE.md`). Then run from `/opt/gnk`:

```bash
cd /opt/gnk
gnk_compose=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
"${gnk_compose[@]}" up -d --wait postgres redis &&
"${gnk_compose[@]}" -f docker-compose.migrate.yml build migrator &&
./deploy/migrate_database.sh &&
GNK_ENV=production ./deploy/gnk-service.sh start &&
GNK_ENV=production ./deploy/gnk-service.sh health
```

The explicit build makes this work even before the fixed migration script is synced. Read the migration output: the migrator should apply the outstanding revisions. If any step fails, the `&&` chain stops; investigate that error before continuing. There is no need to regenerate credentials or delete existing accounts.

Optional read-only confirmation:

```bash
"${gnk_compose[@]}" exec -T postgres psql -U gnk -d gnk -c 'SELECT version_num FROM alembic_version;'
```

For the current release the result is `0004`. Then retry registration in the browser. If registration advances past the schema error but email delivery fails, inspect the new backend error separately; a successful database migration does not verify external SMTP delivery.
