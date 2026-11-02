# Registration schema repair

Cause confirmed from the supplied VM logs: `users.gender` is missing because the new backend was started against an older database schema.

The source fix rebuilds the separate migrator image before upgrading, checks migration/schema readiness at startup and in health/environment probes, and suppresses SQL bound values in application exceptions.

After a database backup, run on the Oracle VM:

```bash
cd /opt/gnk
gnk_compose=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
"${gnk_compose[@]}" up -d --wait postgres redis &&
"${gnk_compose[@]}" -f docker-compose.migrate.yml build migrator &&
./deploy/migrate_database.sh &&
GNK_ENV=production ./deploy/gnk-service.sh start &&
GNK_ENV=production ./deploy/gnk-service.sh health
```

The explicit migrator build works with the older script too. The latest expected migration is `0004`; `0003` supplies the missing user profile columns. Existing accounts and database volumes are preserved.

To deploy the new readiness protection as well, sync the source update first and use the existing full production deployment workflow.

Validation: an integration regression starts at migration `0002`, confirms readiness/health fail, upgrades to head, preserves an existing user's password hash, and successfully registers, verifies, signs in and reads the new profile fields. A second test proves that stamping a revision cannot hide a missing column. Real PostgreSQL and Linux-only checks are covered by CI, not claimed as locally run.
