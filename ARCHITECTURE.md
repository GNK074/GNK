# GNK ALGO architecture

The deployment is a modular FastAPI monolith with React, PostgreSQL, Redis and SMTP. Existing AI/quant/backtesting/worker directories remain extension boundaries, not runnable services. See TECHNICAL_AUDIT.md for the pre-change audit and IMPLEMENTATION_STATUS.md for remaining scope.

Frontend: components/pages/layouts provide public/account navigation; services owns cookie API/CSRF handling; brokers shows masked independent accounts and approved authentication modes; strategies/PaperWorkspace implements manual paper research; admin/BrokerApprovals records reviewer evidence; MFA enrollment is a restricted session flow. Client visibility never grants backend permissions.

Backend: core owns validated settings/lifespan; database owns pooled synchronous psycopg sessions and transaction-local tenancy; models contains identity and trading records; security owns Argon2/JWT/CSRF/MFA, field encryption and ownership helpers; api owns account routes; brokers owns registry, Upstox auth/profile, callback state and approval reviews; execution owns paper orders/positions and a blocked live-order guard; risk owns persistent user emergency stop; notifications owns existing SMTP transport.

Dependency direction is routes -> schemas/security/services -> models/database/core. Encrypted token payloads bind owner and account IDs. Composite foreign keys enforce account/strategy ownership. Forced RLS protects new owned tables in PostgreSQL under a restricted runtime role; identity/session authorization remains enforced in backend queries. Callback access resolves its tenant through exact hashed state, never a browser user_id.

Migrations are frozen in database/migrations. Dev startup may migrate inline. Production mounts owner credentials only into PostgreSQL and a one-off migrator; API uses gnk_app and rejects superuser/BYPASSRLS. Secrets are generated exclusively into new protected files. Infrastructure templates do not modify the remote VM automatically.

Live approval: 18 current reviewer evidence records are necessary but insufficient while execution/reconciliation are unavailable. Global settings cannot enable real-money orders. The paper engine accepts explicit research prices, locks per-user state, applies personal limits and idempotency, updates long-only positions/P&L and respects user/platform stops. It is not a realistic exchange simulator.

Tests separate application isolation, adapter HTTP contracts, configuration/encryption, mocked Linux service orchestration and an optional real PostgreSQL RLS job. Local results and unexecuted production checks belong in VALIDATION.md. Backend workers, licensed market streams, static IP monitoring, other broker adapters, live execution/reconciliation and broker-side cancellation remain unimplemented.
