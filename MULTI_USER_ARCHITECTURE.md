# Multi-user isolation

Each new user-owned model has user_id -> users.id. Broker credentials/auth states reference (account_id,user_id) through a composite foreign key; orders reference (strategy_id,user_id). Unique broker/account identity prevents assigning the same customer broker account to different platform users. API queries use the authenticated user, never a browser-supplied owner.

Migration 0002 adds broker_integrations, broker_accounts, broker_credentials, broker_auth_states, strategies, risk_configurations, orders, positions, platform_controls and five approval tables. PostgreSQL forced RLS protects the new user-owned tables. The runtime DB role must not be a superuser or BYPASSRLS. Auth sets transaction-local app.user_id, and the SQLAlchemy session event reapplies it after commits while a new session defaults to no tenant. Callback state lookup is permitted only for its exact hashed state context; after validation the callback adopts the stored owner. Application filters remain mandatory in addition to RLS.

Global integration/application approval records are server-admin/operator controlled, not customer-owned. Identity/session tables retain existing explicit ownership checks; the change does not claim that all historical tables have RLS. The API role is trusted backend infrastructure and can set transaction context; do not give it to end users or expose the DB network.

Three-user API tests cover broker connections, credential envelope binding, order/position reads, strategy edits, forged owners, risk isolation, live broker ownership and admin rejection. SQLite validates application behavior. A separate PostgreSQL CI test checks forced policies, transaction context reset and composite ownership FKs using a restricted role. That CI job has not been executed on this workstation.

Not yet implemented: independent broker WebSocket sessions, holdings/trades/notification tables, real portfolio synchronization, licensed market-data distribution, strategy workers and live order reconciliation. These remain production blockers, not simulated capabilities.
