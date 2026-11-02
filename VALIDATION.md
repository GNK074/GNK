# Validation — multi-user security update (2026-11-02)

Executed locally on Windows/Python 3.14:

- Backend suite: 22 passed, 14 skipped. Passing coverage includes account flows, three-user isolation, credential encryption/owner binding, callbacks/state replay/expiry/exchange errors, same-owner reauthorization, disconnect ownership, personal risk limits, paper idempotency/realized loss/stops, blocked live broker ownership, MFA/replay, all-18 approval rechecks, settings/encryption, provider HTTP contracts, secret generation/non-overwrite, independent rate-limit buckets and fail-closed Redis behavior.
- After the final approval-status persistence change, the targeted all-18 gate test passed again.
- Populated migration 0001 -> 0002 passed against an isolated SQLite database. Legacy account/hash preserved; old sessions revoked; resulting schema matches ORM metadata.
- Frontend TypeScript/Vite production build passed.
- Python syntax compilation passed.
- All 16 Bash scripts parsed with the Tree-sitter Bash grammar and use LF. This does not substitute for execution under Bash/Docker.
- Base, production, migration Compose and GitHub Actions YAML parsed.

Skipped/not executed:

- 13 Linux Bash command-contract tests: no functional Linux Bash in this Windows sandbox. Ubuntu CI is configured to run bash -n across scripts and the Docker/curl test doubles.
- 1 actual PostgreSQL RLS/constraint test: no PostgreSQL/Docker service locally. A dedicated PostgreSQL CI job is configured, but its outcome has not been observed.
- No real Docker build/boot, Redis authentication, restricted-role PostgreSQL boot, GPG backup/restore, real SMTP, DNS/TLS, browser automation, Oracle VM deployment, broker sandbox/customer authorization, licensed feed, live order or production security/compliance review was executed.
- One Starlette/httpx deprecation warning remains in test infrastructure; it did not fail the tests.

No real-money order was submitted. Infrastructure readiness is not live-trading approval. See IMPLEMENTATION_STATUS.md for remaining work and PRODUCTION_DEPLOYMENT.md before modifying an existing server.


## Redis startup regression fix

The original secure startup assumed su-exec and reused a chowned config path. The reported VM logs proved that assumption invalid. The fix delegates privilege dropping to the official image entrypoint and creates a unique private config directory per start; production Redis mounts /tmp as tmpfs. No persistent volume is removed.

Updated startup Bash grammar and Compose/CI YAML parsing passed locally. A real Redis container smoke test now checks unauthenticated rejection, authenticated PING, restart and data persistence in Ubuntu CI using an isolated disposable test volume. That Docker test has not run locally; its CI outcome has not been observed.


## Mounted-secret permission regression

The reported backend startup failed before database connection because the non-root API could not read /run/secrets/app_db_password. Added an operator check/repair for the three configured direct files under secrets/, preserving values and refusing external/missing sources. The production deployment helper checks permissions before proceeding; backend read failures now identify the repair command without printing values. Seven targeted tests passed (three permission regressions plus four settings/encryption/adapter tests). Actual UID/file access on the Oracle VM must be verified with a one-off non-root backend shell; Docker is unavailable locally.


## Startup dependency diagnostics

The next VM attachment ended at lifespan.py without the final exception message. No database/Redis root cause can be inferred from that truncated trace. Startup checks now distinguish PostgreSQL authentication/authorization/missing database/privilege/connectivity failures, privileged runtime roles, and Redis authentication/connectivity failures without exposing driver messages or values. Added backend/check_startup.py. Seven targeted diagnostic tests passed locally. Actual VM dependency checks remain pending its diagnostic output.


## Individual broker setup update

Implemented account-inspection handlers for Dhan, Zerodha, Upstox, Angel One, FYERS, 5paisa and ICICI Direct. Documentation references and per-provider required fields are in INDIVIDUAL_BROKER_SETUP.md. No customer credentials were available or used during development. No real provider connection or order was made by these tests.

Full local backend suite: 53 passed, 14 skipped. Twenty initial targeted tests cover seven HTTP contracts and failures, token expiry, operator IP requirements, per-user encrypted saves, identity/consent rejection, secret redaction and operator disable. Added a regression for unreadable saved sessions to require reauthorization instead of being counted connected. The dashboard, legacy connection listing and current connection listing use user-owned records.

Frontend TypeScript/Vite production build passed after the new forms and dynamic dashboard. Existing schema 0002 is unchanged; no migration is introduced by this update. Fourteen environment-dependent Linux/PostgreSQL tests remain skipped locally; their CI results have not been observed. Live execution remains disabled. Five non-primary catalog candidates still lack implemented validators. Deployment of this update to the public VM has not yet been performed.
