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
