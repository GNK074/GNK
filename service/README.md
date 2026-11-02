# GNK ALGO service operations

Run these commands on Ubuntu from the project root:

```bash
chmod +x deploy/gnk-service.sh service/gnk-service.sh
cp .env.example .env
# Edit .env: configure independent random JWT_SECRET and POSTGRES_PASSWORD.
./deploy/gnk-service.sh build
./deploy/gnk-service.sh start
./deploy/gnk-service.sh status
./deploy/gnk-service.sh health
./deploy/gnk-service.sh logs
./deploy/gnk-service.sh stop
./deploy/gnk-service.sh deploy
./deploy/gnk-service.sh urls
```

Requirements: Bash 4.3+, Docker Engine, Docker Compose v2.24.4+, curl, and permission to access the Docker daemon. Scripts resolve the repository root from their own location and can also be called by absolute path from another directory. `service/gnk-service.sh` is the implementation; `deploy/gnk-service.sh` is the stable entry point. Compose continues to work directly.

`start` creates/starts the complete Compose project and waits for readiness. Missing application images may be built by Compose. `build` builds application images without starting containers. `deploy` builds then recreates changed services, with the backend entry point applying migrations. It does not git-pull, change source, erase volumes, or promise a zero-downtime deployment. Back up the database before schema changes; restoring an older image alone does not undo migrations.

`stop` uses Compose stop, preserving containers, networks and volumes. It is not a broker-side emergency cancellation command. `status` displays all containers, URLs and readiness; it returns a nonzero exit code for missing, stopped or unhealthy services. `health` checks each expected container and requires HTTP 200 from the application root and API health endpoint. The API health endpoint exercises PostgreSQL and Redis. Services without a Docker healthcheck produce a warning, not a false readiness guarantee. HTTP probes do not exercise authentication, real SMTP delivery, or any broker.

`logs` follows all services with timestamps and the last 200 lines. Press Ctrl+C to exit without stopping services. Use `./deploy/gnk-service.sh logs backend nginx` to select services, or `GNK_LOG_FOLLOW=0 ./deploy/gnk-service.sh logs` for a snapshot. Treat application logs as operational data; do not post secrets from unrelated application output.

## Production

Set `ENVIRONMENT=production`, `FRONTEND_URL=https://your-domain`, and real SMTP variables in `.env`. The script automatically includes the production override. You can also explicitly select it with `GNK_ENV=production`. Production configuration requires an external TLS-terminating reverse proxy forwarding to server loopback port 8080. The script does not install certificates, open firewall ports, publish DNS, or change network exposure. Mailpit remains an internal development container in the current Compose topology; production SMTP points to your configured provider, not Mailpit. Its inbox is bound to loopback and omitted from production URL display.

Examples:

```bash
GNK_ENV=production ./deploy/gnk-service.sh deploy
GNK_PUBLIC_URL=https://gnkalgo.example ./deploy/gnk-service.sh urls
GNK_HEALTH_URL=http://127.0.0.1:8080 ./deploy/gnk-service.sh health
GNK_WAIT_TIMEOUT=300 ./deploy/gnk-service.sh start
```

`GNK_PUBLIC_URL` changes display/probe URLs; it does not reconfigure application CORS or cookie origin. Keep FRONTEND_URL consistent with the actual browser origin. `GNK_HEALTH_URL` changes only the probe origin. Do not use a loopback probe as evidence that public DNS/TLS works. `/admin` requires an administrator account; bootstrap with `docker compose exec backend python bootstrap.py` after migration. `/docs` enumerates every API endpoint, including protected admin routes. Verification and reset pages require the one-time token from email.

The dotenv reader handles plain or wholly quoted KEY=value lines. Use ordinary assignments without `export`, interpolation or inline comments for ENVIRONMENT and FRONTEND_URL. It never executes the file. Docker Compose remains authoritative for application environment interpolation.
