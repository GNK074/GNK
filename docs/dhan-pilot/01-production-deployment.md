# Deploy the Dhan pilot on the Oracle VM

1. Sign in to the VM and run the following checks. The pilot commit is `0208d97dfa70801c7c456fca29c7d28fb8743c15`. Review local edits if Git reports any. Keep the previous running release available for rollback.

```bash
cd /opt/gnk
git status --short
git log -1 --oneline
GNK_ENV=production ./deploy/gnk-service.sh health
```

2. Pull, verify that the checkout contains the pilot, and build the affected images. The pilot commit adds no migration. If the validation script reports a schema mismatch, stop before replacing containers and follow the database backup and migration procedure for the installed release.

```bash
(
  set -e
  cd /opt/gnk
  git pull --ff-only
  git merge-base --is-ancestor 0208d97dfa70801c7c456fca29c7d28fb8743c15 HEAD
  dc=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
  "${dc[@]}" build backend frontend
  ./deploy/validate_environment.sh
  "${dc[@]}" up -d --no-deps --wait --wait-timeout 180 backend frontend
  "${dc[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 60 nginx
  GNK_ENV=production ./deploy/gnk-service.sh health
)
```

3. Sign in and open [Dhan pilot](https://gnkalgo.com/user/brokers/dhan-pilot). If the VM already contains the commit and the page works, record the result and continue to configuration. If a rebuild fails after replacement, restore the previous known-good backend and frontend images using your deployment runbook, recreate Nginx, and repeat the health check.
