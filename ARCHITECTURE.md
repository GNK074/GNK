# GNK ALGO architecture

## Shape and runtime

Start as a modular monolith: one FastAPI process, one frontend, PostgreSQL, Redis and SMTP. AI training and historical research are separate offline workloads. Worker processes are reserved boundaries and are not started by Compose until actual job handlers exist. This keeps database transactions and session revocation consistent without introducing premature network services.

Browser -> Nginx -> React static assets or FastAPI /api/v1 routes.
FastAPI -> PostgreSQL for identity, sessions, token digests and audits.
FastAPI -> Redis for authentication throttling.
FastAPI -> SMTP for verification and recovery emails.

## Frontend ownership

- components: reusable presentation such as Logo; no direct database or broker access.
- pages: public landing, authentication and account settings.
- layouts: application shell, protected navigation and page selection.
- dashboard: account-level summary; unknown values stay unavailable rather than fabricated.
- brokers: candidate discovery and setup status; credentials are never saved in browser storage.
- risk-management: current account-session UI; future limits and trading controls require backend enforcement.
- admin: role-protected administrative views; backend authorization remains authoritative.
- services: same-origin HTTP client, credential cookies and in-memory CSRF handling.
- store: shared session types; bearer tokens must not be persisted in browser storage.
- markets, strategies, backtesting, ai-insights, quant-lab, portfolio: reserved feature boundaries. Build feature-specific pages and API clients here when their services exist.

Use TypeScript components with named exports and feature-local helpers. Share stable UI primitives through components. Avoid cross-feature imports when a small shared type or API contract is sufficient.

## Backend ownership

- api: authentication, user and health routers; handlers orchestrate validated requests.
- core: environment configuration, clock, identifiers and token digest helpers.
- database: engine, session factory, declarative base and request transaction scope.
- models: identity persistence entities. All models load before migration metadata inspection.
- schemas: Pydantic inputs and password validation.
- security: JWT verification, authenticated dependencies, roles, CSRF and Redis throttling.
- services: account token issuance/consumption, revocation, public projections and audits.
- notifications: SMTP transport. A durable outbox is a future improvement.
- brokers: independent adapter contract, explicit empty approved registry and blocked connection routes.
- dashboard: disconnected workspace summary aggregate.
- risk: emergency-stop audit endpoint; no order cancellation is claimed.
- admin: user listing, account status, role changes, audit logs and system health.
- market_data, strategies, execution, portfolio: reserved domain implementations.

Dependency direction: routes -> schemas/security/services -> persistence/core. Models import database Base and core helpers. Core does not import routes. Research libraries must not import the FastAPI application or HTTP authentication dependencies.

## AI engine

Reserved, not implemented. data_pipeline owns timestamped dataset ingestion and provenance; feature_engineering transforms only data available at decision time; models owns model definitions; training owns reproducible fitting; inference owns versioned prediction contracts; evaluation owns out-of-sample and drift checks; model_registry owns model versions, dataset hashes, metrics and approval status. A model prediction is advisory input, never authorization to submit an order.

## Quant engine

Reserved, not implemented. indicators owns deterministic indicators; statistical_models owns research estimators; volatility owns volatility calculations; options_analytics owns pricing/Greeks with explicit model assumptions; portfolio_optimization owns constrained allocation; signal_research owns reproducible signal experiments. Modules should be pure Python libraries with explicit units and no broker credentials.

## Backtesting

Reserved, not implemented. engine owns event ordering and replay; simulators owns fills, fees, slippage and liquidity assumptions; optimization owns parameter search; walk_forward owns chronological training/validation splits; reports owns metrics and reproducible result export. Historical results must identify the dataset, parameter version and execution assumptions. Research results must not be presented as live returns.

## Workers and future execution flow

Reserved, not implemented. market_worker ingests authorized market events; strategy_worker evaluates approved strategies; execution_worker consumes only risk-approved order intents; scheduler triggers maintenance/research jobs. Define versioned job payloads, idempotency keys, bounded retries and dead-letter handling before connecting a queue.

Future path: authorized feed -> strategy intent -> risk decision -> approved broker adapter -> order reconciliation -> portfolio update -> audit. Execution must reject intents when emergency stop, user authorization, broker eligibility or required risk approval is absent. No part of this path is enabled by the current scaffolding.

## Data, deployment and tests

- database/migrations is the sole Alembic revision location. Revision 0001 freezes the existing identity schema. Add revisions for future schema changes; do not rewrite deployed revisions.
- database/schemas is reserved for schema documentation; database/seeds is reserved for idempotent non-secret seed data. Administrator setup remains the interactive backend/bootstrap.py command.
- infrastructure/docker owns the frontend/backend Dockerfiles. Compose builds from the repository root so backend migrations are included.
- infrastructure/nginx owns the application reverse proxy. monitoring and deployment are reserved for actual operational configuration.
- tests/integration contains isolated authentication flow tests. tests/unit contains service-manager contract tests using mocked Docker/curl on Ubuntu. security and end_to_end remain reserved for meaningful additions; empty folders do not constitute coverage.

## Current capability boundary

Identity and account workflows are implemented. Twelve brokers are candidates, not supported integrations. No live feed, AI predictor, quantitative engine, backtester, strategy execution or trading worker is implemented. No order endpoint exists. Review README.md for remaining production requirements and VALIDATION.md for actual verification evidence.


## Service control layer

`deploy/gnk-service.sh` delegates to `service/gnk-service.sh`. Commands construct Compose argument arrays, never execute .env contents, preserve volumes, and return nonzero for failed commands or failed health checks. Development uses the base Compose file; production adds the production override. Application and admin URLs are displayed without claiming unauthenticated access to protected routes. Docker readiness probes cover PostgreSQL, Redis, backend, frontend and Nginx; Mailpit currently has no container probe and is reported as a warning. Real SMTP delivery and external HTTPS require separate verification.
