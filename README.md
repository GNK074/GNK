# GNK ALGO

React/TypeScript + FastAPI/PostgreSQL application for isolated user accounts, broker authorization management, paper research and evidence review. Domain: gnkalgo.com; proposed broker callback host: api.gnkalgo.com.

## Implemented

Email verification/recovery, Argon2 passwords, cookie JWT and hashed rotating refresh sessions, CSRF, RBAC, TOTP MFA enrollment/replay protection, encrypted per-user/account credential envelopes, tenant-owned broker/strategy/risk/order/position models, additive migration 0002 with forced PostgreSQL RLS, Upstox OAuth/profile adapter behind an operator-reviewed registry, single-use callback state, manual long-only paper orders with risk limits/idempotency, persisted stops and a hard 18-requirement broker approval gate. React includes account, MFA, broker status/setup, paper workspace and super-admin evidence review.

## Development start

Install Docker Engine/Compose >=2.24.4, Bash, curl and Python 3. Generate a new profile with `bash deploy/generate_secrets.sh --output .env.generated`; review and copy it to .env without replacing existing secrets. Then run `docker compose up -d --build` or `./deploy/gnk-service.sh start`. Visit http://localhost:8080, development mail at http://localhost:8025, and API documentation at http://localhost:8080/docs. Register, verify via captured email, and sign in. Development MFA is optional; production requires it.

Production follows PRODUCTION_DEPLOYMENT.md, with encrypted backups, restricted runtime DB role and separate migrator. Never replace an existing database password or encryption key by generating a fresh profile. Never delete production volumes.

## Checks

Frontend: `cd frontend && npm ci && npm run build`.
Backend: Python 3.12+, install backend/requirements.txt, set PYTHONPATH=backend and run `python -m pytest tests -q` from the root. Tests use test-only profiles and captured SMTP. Linux service command tests mock Docker/curl; they are not container boot tests. PostgreSQL-specific RLS tests run only when GNK_TEST_POSTGRES_URL points to an isolated disposable database, as configured in CI. See VALIDATION.md for executed results.

## Operations

`./deploy/gnk-service.sh start|stop|build|deploy|status|logs|health|urls`. See service/README.md. Production helper scripts live in deploy/; configuration/secret validation is under infrastructure/env/. Bootstrap an administrator interactively using backend/bootstrap.py inside the configured backend container. No administrator credentials are hardcoded.

## Important capability limits

Live execution is unavailable and cannot be activated through an environment flag or evidence count. Seven individual account validators have mocked HTTP tests, not verified real-customer integrations. Only Upstox has the separate automatic OAuth adapter; remaining catalog candidates and other complete OAuth flows are pending. There is no live feed, licensed market-data distribution, real portfolio synchronization, order reconciliation, broker-side emergency cancellation or production worker implementation. Paper fills use manually entered prices and omit margin, fees and slippage.

Oracle VM deployment, DNS/TLS, real SMTP, actual PostgreSQL/Redis operation, restored backups, external security/compliance review and official broker approvals have not been verified from this environment. Do not describe this build as production-ready or approved for real-money trading. IMPLEMENTATION_STATUS.md separates implemented code from remaining external and development work.

Read TECHNICAL_AUDIT.md, MULTI_USER_ARCHITECTURE.md, ENVIRONMENT_VARIABLES.md, BROKER_INTEGRATION.md, SECURITY_CONFIGURATION.md and PRODUCTION_GO_LIVE_CHECKLIST.md before deployment.

## Connect individual broker accounts
Use your own API application/session credentials through the broker setup forms. Seven provider-specific identity validation handlers are available; see INDIVIDUAL_BROKER_SETUP.md for exact fields, documentation, operator requirements and unimplemented catalog candidates. Connected status requires successful provider validation and does not enable live execution. The dashboard uses actual per-user connection records.


## Profile and settings

`/user/settings` includes editable personal details, private photo upload/reset, password and email changes, session revocation, and three account-saved themes. Login and registration use the supplied GNK brand artwork. See [PROFILE_SETTINGS.md](PROFILE_SETTINGS.md) for API contracts, validation, migration and deployment instructions.

## Risk disclosure and contact

A server-recorded, per-login risk acknowledgment now gates the dashboard and all order submissions. `/contact-us` provides a responsive public support page with verified-publication controls. Migration `0004` is required. See [DISCLOSURE_CONTACT.md](DISCLOSURE_CONTACT.md) for deployment, regulatory-source review, configuration, and validation limits.

## Authenticator QR setup and recovery

Login includes Forgot MFA; setup generates a local QR code and one-time recovery codes. Workspace pages use only the selected Appearance theme. Migration `0005` is required. See [MFA_RECOVERY.md](MFA_RECOVERY.md) for the backup-code/email and reviewed-administrator recovery paths, deployment and validation.

## Phase 05 market data

See [MARKET_DATA_PHASE05_REPORT.md](MARKET_DATA_PHASE05_REPORT.md) for API contracts, offline verification, migration and controlled activation. Shared Upstox data remains disabled by default pending review of the written distribution scope and live acceptance tests.

## Controlled Upstox live execution

See [UPSTOX_LIVE_EXECUTION.md](UPSTOX_LIVE_EXECUTION.md) for the NSE equity intraday limit-order scope, migration 0007, reconciliation worker, API contracts and activation/rollback. Samples remain disabled; broker acceptance and user/account approval are separate from environment validation.

## Trade details

[Orders, Trade History and Signals](TRADE_DETAILS.md) documents the new pages, owner-scoped reporting, fill-based gross P&L, Excel export and migration 0008. Live execution settings are unchanged.
