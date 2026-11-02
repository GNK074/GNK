# Docker and service controls

Existing commands remain ./deploy/gnk-service.sh start, stop, build, deploy, status, logs, health and urls. The runner detects APP_ENV/legacy ENVIRONMENT, validates Compose configuration and checks container/HTTP state. Stop preserves volumes. Logs support service filters and GNK_LOG_FOLLOW=0. Health does not prove real SMTP, broker connectivity, public DNS/TLS or licensing.

Production uses docker-compose.yml + docker-compose.prod.yml. The production API command no longer migrates with owner credentials. Use deploy/migrate_database.sh, which adds docker-compose.migrate.yml and runs an ephemeral migrator. Dev startup retains the existing migrate-and-start entry point. Existing volume names and service keys are preserved; no duplicate fake market/AI/execution workers are started.

Database, Redis and API health checks are real container probes; frontend/Nginx use HTTP checks. Mailpit remains a loopback-bound development inbox in the current topology, unused by production SMTP. Memory/resource sizing and production monitoring need host measurement; do not assume capacity from these defaults. No market-data/strategy/execution/AI worker containers are shipped because their production handlers are not implemented.

GNK_ENV=production ./deploy/gnk-service.sh deploy is an application operation after reviewed role/migration/infrastructure preparation. Prefer deploy/deploy_production.sh for an existing prepared installation, including encrypted backup. Never use docker compose down -v on a populated deployment.
