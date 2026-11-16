# Proposed implementation architecture

## Repository and impact

Reviewed GNK revision 9d90ba1. React 19, Vite 6, TypeScript, React Router and Lucide render the workspace. FastAPI 0.115+ with SQLAlchemy, PostgreSQL and Alembic serves the API. Docker Compose on OCI runs the app, Redis and workers. Reuse existing session authentication, MFA, ownership checks, static-IP review, audit logging and notifications. The former Broker Setup route was removed and onboarding is disabled by environment settings.

BrokerIntegration, BrokerAccount, BrokerCredential, BrokerAuthState and Dhan ConsentAttempt already represent catalogue configuration, account identity, encrypted broker secret material and authorization state. Dhan consent and read-only account operations have existing implementations. FYERS has a profile verifier. Upstox has OAuth and separate execution and market-data components. A catalogue listing does not establish account permissions or live connectivity. Redis and separate WebSocket paths support existing workers and streams.

## Implementation and migration

1. Finish authenticated discovery, then update parity and validate official provider contracts.
2. Design the new workspace using the existing UI. Add the Lucide BrainCircuit mark with violet/cyan glow and reduced-motion support.
3. Extend existing accounts and adapters for status, configuration and ownership. Keep encrypted credential handling within the server. Use additive Alembic migrations only for confirmed missing metadata or permission evidence. Backfill without changing account IDs or affecting order history.
4. Separate requested segments, broker-supported capabilities, broker-confirmed permissions and execution eligibility. Reuse GNK IP review and record broker-side whitelisting independently.
5. Validate Dhan first, then FYERS and Upstox. Test callback replay, cross-user isolation, revocation, token expiry, IP restrictions and execution blocking. Use provider fixtures and authorized sandbox or test accounts.
6. Keep live execution gated. Verify the migration and restore path in an isolated PostgreSQL environment. Roll back application images independently where schema compatibility permits, and preserve account and audit history.

Broker approvals, provider support and exchange-specific restrictions must be verified before production activation.

## Environment verification

OCI active .env and the tracked production example have the same key set and no duplicates. The development example has no duplicates. The inactive historical .env backup still contains three duplicate Upstox assignments. Production application, market data, PostgreSQL schema and Redis validation passed. Individual broker onboarding, Dhan OAuth, Dhan execution and global live execution are disabled in both tracked templates and the active OCI file. No environment changes are needed for the discovery phase.
