# GNK ALGO

A functional initial release of the supplied project plan: React/TypeScript frontend, FastAPI backend, SQLAlchemy database models, Alembic initialization, PostgreSQL, Redis rate limiting, SMTP verification and password reset, cookie-based JWT sessions, CSRF checks, server-enforced roles, account management, admin API, broker candidate catalog, and disconnected dashboard.

This is an initial implementation, not completion of every production requirement in the plan. Broker integrations are explicitly pending verification. There is no market feed, AI signal engine, portfolio data source, or order execution. No fabricated prices or performance are presented. The source agreement's personal acceptance certificate is not included in the application.

## Run with Docker

1. Install Docker Desktop with Docker Compose v2.24.4 or newer.
2. Copy `.env.example` to `.env`.
3. Replace JWT_SECRET and POSTGRES_PASSWORD with independently generated random secrets. Use a URL-safe database password.
4. From this directory: `docker compose up -d --build`.
5. Open http://localhost:8080. View development verification/reset emails at http://localhost:8025. API documentation: http://localhost:8080/docs.
6. Register, open the Mailpit email, verify, sign in, explore broker availability, and continue to the dashboard without a connection.
7. Bootstrap an administrator interactively: `docker compose exec backend python bootstrap.py`. Credentials are never hardcoded.

Mailpit is development-only email capture. Configure real authenticated SMTP before deployment. SMTP failure prevents the registration transaction from committing; retry after correcting SMTP. Emails are synchronous in this release; a durable outbox/background worker is still required.

## Development

Frontend: `cd frontend`, `npm ci`, `npm run dev`. Vite proxies /api to a local backend on port 8000. Set FRONTEND_URL=http://localhost:5173 for that development arrangement.
Backend: Python 3.12+, `pip install -r requirements.txt`, configure environment, `alembic upgrade head`, then `uvicorn app.main:app`. JWT_SECRET must be set before any backend command, including migrations.
Tests: from the repository root, set PYTHONPATH=backend, then run `python -m pytest tests -q`. Tests use isolated in-memory SQLite, a captured email sender, and a bypassed rate limiter. Production Redis and PostgreSQL require separate integration verification.

## Deployment

The requested Python/PostgreSQL service cannot execute in Sites' Cloudflare Worker runtime. The deliverable is a self-hosted Docker project; no website has been published.

Use `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build` behind a TLS-terminating reverse proxy forwarding to loopback port 8080. Set FRONTEND_URL to the exact HTTPS origin; set real SMTP variables. The production override enables Secure cookies, HSTS, and SMTP STARTTLS. TLS certificates and the external HTTPS reverse proxy are operator-managed and are not bundled. Keep the SMTP UI inaccessible to remote users. PostgreSQL and Redis have no published host ports.

Never run `docker compose down -v` on a populated deployment. Back up PostgreSQL using `pg_dump`, encrypt backups, store them off-host, define retention, and perform restoration drills before launch. Preserve JWT_SECRET between restarts. Rotate it intentionally to invalidate access tokens.

## API behavior

OpenAPI provides endpoint schemas. All protected writes require X-CSRF-Token returned by sign-in or GET /api/v1/users/me. JWT access lasts 15 minutes; refresh sessions expire after 30 days, rotate their token on refresh, and are checked server-side on protected requests. Tokens are stored as hashes; access and refresh cookies are HttpOnly and SameSite Strict. The React app keeps CSRF only in memory. Expired access currently requires signing in again in the UI; refresh is exposed through the API.

Logout currently revokes all devices for both logout endpoints. Verification and reset tokens are single use. Account discovery responses are generic. Authentication endpoints fail closed when Redis is unavailable. SMTP send failures require retry. Admin role changes require SUPER_ADMIN. Bootstrap creates one verified SUPER_ADMIN through an operator-controlled command.

## Remaining production scope

- Official broker adapter implementations, encrypted credentials, OAuth/PKCE callbacks, permission tests, renewal/revocation, and broker sandbox tests. No broker is currently supported; credential endpoints return HTTP 409.
- Legal/regulatory verification, configurable compliance policies, pre-trade risk engine, execution and emergency cancellation integration. Emergency stop currently records an audit event; there are no running orders to cancel.
- MFA, permissions/roles normalization, complete broker-related schema, notification logs, durable email outbox, configuration management, deactivation UI, mobile field, remember-me preference, admin edit UI, pagination, and monitoring integrations.
- Future schema changes require new incremental Alembic revisions. The initial migration now contains frozen table definitions.
- Per-account progressive lockout, distributed session replay-family detection, periodic session/token cleanup, endpoint-wide security testing, load tests, browser/component automation, security review, and production PostgreSQL/Redis/TLS deployment verification.
- Full legal/privacy documents and explicit versioned agreement acceptance records. Signup consent copy is a development placeholder requiring owner/legal review.
- Dependency/version audit, release pinning, secret management integration, automated encrypted backups and restore validation, and non-root frontend/reverse-proxy hardening.

Do not describe this release as approved for live trading or production-ready until those items and the plan's acceptance criteria have been completed and reviewed.



## Modular project layout

The project follows the requested GNK-ALGO monorepo layout. Frontend components and pages are separated from API access and session types. Backend modules separate HTTP routes from authentication, account services, schemas, persistence and notifications. New AI, quantitative research, backtesting and worker directories are explicit extension boundaries; reserved modules contain README files and do not imply implemented features.

Migrations: `database/migrations`. Operational images: `infrastructure/docker`. Reverse proxy: `infrastructure/nginx`. Integration tests: `tests/integration`. Root Compose commands remain unchanged after the reorganization.

See ARCHITECTURE.md for dependency rules and module ownership.
