# GNK Algo — Dhan technical assessment and implementation roadmap

Assessment date: 5 November 2026. Reference revision: `8c6583e6e169fd0293e2271cb5fcb5aad3f8e805`. The full reference checkout is kept outside the application under the development work directory; it is not a replacement application or a production dependency. The pinned official package remains dhanhq 2.3.0.

## Assessment method

All 98 readable reference source/test/example/configuration files (7,417 lines) were read by the inventory pass; Python AST analysis enumerated public methods, signatures and endpoint literals. Runtime modules, authentication, network transport, binary parsers, order updates, package/dependencies, license, examples and publishing workflows were inspected. `docs/dhan-sdk-feature-map.json` records every public SDK method/helper and file hashes/line references. The reference is a broker SDK, not a complete multi-user platform: it has no GNK authentication, tenant isolation, durable execution database, risk policy or production UI.

## Existing GNK Algo versus reference

GNK already has React/TypeScript/Vite, FastAPI, PostgreSQL tenant RLS, encrypted broker credentials, CSRF/MFA, audit logs, Redis, portfolio snapshots, financial exports and Docker deployment. Dhan SDK account/quote/history/option reads already exist. The execution ledger/reconciliation, production approval and live entry UI are Upstox-specific; the shared market-data worker and upstream instrument namespace are also Upstox-specific.

The SDK adds available API payload builders and binary packet parsers. Its direct `place_order` is not durable orchestration: it does not implement GNK idempotency, risk ownership, crash recovery, independent reconciliation or permission gates. Those remain GNK responsibilities.

## Complete capability groups

- Authentication: individual tokens, renewal, profile, app consent login/token exchange, PIN/TOTP generation and static IP reads/mutations. GNK token verification/renewal exist; consent login needs application-bound attempts and callback replay protection. Broker TOTP enrollment is distinct from GNK MFA.
- Portfolio/account: holdings, net positions, fund limits, position conversion/exit, EDIS/TPIN, single/multi-leg margin estimation and ledger. Existing normalized snapshot services should be reused; broker writes need explicit workflows.
- Orders: book/detail/correlation lookup, regular/sliced placement, modification/cancellation, per-order trades and historical trades. Reuse GNK durable order intents, risk configuration, account/strategy authorization and fill accounting.
- Market data: REST LTP/OHLC/quote, binary ticker/quote/full packets, dynamic subscription changes, previous close/OI/status and disconnect codes. Add private account-scoped streams rather than sending Dhan customer tokens to browsers or merging them into a shared Upstox feed.
- Options/history: expiry lists, chains, IV/Greeks/bid/ask/OI, daily/intraday candles and expired-option rolling data. Most reads exist; additional endpoints can extend the same validated owner-bound service.
- Monitoring: JSON order-update socket and REST reconciliation. Stream updates should wake/describe monitoring, not become unverified fill records or cause placement retries.
- Advanced order families: Super, Forever/OCO, Conditional and P&L exits. Each needs a distinct order-state/risk model, explicit configuration and tests; do not route them through an ordinary LIMIT intent.
- Depth: 20/200-level feeds have separate entitlements, payload sizes and connection budgets. Default quote depth is not equivalent to these products.
- Global stocks: separate instruments, fund limits, market status, order types and live trade/OHLC feeds. Current INR-only accounting is incompatible with simply adding USD balances; defer until multi-currency ledgers/risk are implemented.
- SDK plumbing: context, HTTP helpers, timestamp conversion, subscription packing and binary parsing are implementation components, not independent product features.

## Security/performance findings

1. The reference order-update implementation prints its subscription/authentication message including the access token. It must not be run unchanged on a production server. GNK will use a secret-safe connection loop with the same documented protocol and a sanitized projection.
2. SDK authentication helpers open local browsers and log raw failed response bodies; GNK's server callback/session workflow must replace those side effects, with encrypted credentials and fixed redirects.
3. Default SDK HTTP requests have broad exceptions/raw remarks and weak transport boundaries. Existing GNK guarded transport remains authoritative: fixed paths/hosts, no redirects, bounded bodies/timeouts, sanitized errors, distributed limits and no mutation retry.
4. SDK instrument downloads write filenames and load full dataframes. GNK requires bounded streaming import, schema validation, atomic upsert and provider namespaces.
5. The SDK socket loops are not tenant-aware and can reconnect without GNK ownership/credential fencing. GNK requires per-account leases, credential-version checks, bounded subscriptions, cancellation and fresh/stale/disconnected labels.
6. Reference tests/examples verify SDK behavior, not GNK access control, transaction recovery, concurrency or live-trading policy. New tests must exercise GNK workflows with mocked providers; no real orders are needed.

## Architecture and phased plan

**Phase 1 — assessment:** complete repository inventory, feature mapping and gap/security review before application changes.

**Phase 2 — authenticated account/data foundation:** retain the working SDK reads, verify renewal/account isolation, add provider-specific instrument discovery and improve app-owned capability reporting. No existing trading flag changes.

**Phase 3 — private feeds and monitoring:** add a GNK account-scoped stream worker using official SDK market packet parsing; keep one leased market socket and one order-update socket per account, authenticate browser access without broker tokens, and keep REST as fill truth. Stop publishing after logout/credential replacement/disconnection.

**Phase 4 — guarded Dhan execution:** extend the existing execution dispatch, risk policy and reconciliation interface for verified Dhan instruments. Start with reviewed NSE equity intraday LIMIT/DAY orders; add durable cancel/modify state only when recovery behavior is tested. Preserve Upstox behavior and default Dhan activation to an explicit new operator flag plus existing broker/account/strategy approvals. Never retry an uncertain placement.

**Phase 5 — registered app authentication:** add app-consent attempts bound to user/session/account, encrypted temporary app secrets, one-time callback consumption and profile identity/expiry verification. Do not collect broker TOTP secrets or expose token IDs in application logs.

**Phase 6 — advanced reads and research:** margin estimates, ledger, expired-option data, complete historical paging and options analytics can use owner-bound cached reads. No invented trade-level cost basis, taxes, brokerage or ML probabilities.

**Phase 7 — separately reviewed products:** MARKET/SL/SL-M and additional products/segments, advanced order families, deep feeds, liquidation controls and global stocks require dedicated workflows and validation. Each remains unavailable until its implementation and tests are complete. Trained ML needs actual model artifacts and evaluation data; technical indicators are not a trained model.

## Ownership and licensing

All new application modules, UI, schemas, policies and business logic use GNK Algo identity and existing architecture. Broker names identify integrations only. No reference app/developer branding or copied publishing workflows are introduced. Required third-party MIT notices remain in THIRD_PARTY_NOTICES.md and installed distributions; retaining legal attribution is separate from application branding.

## Delivered implementation and release evidence

Phases 1–5 are implemented in the scoped form above: assessment/inventory, account/data foundation and bounded equity metadata, leased personal v2 streams/order notifications, GNK durable NSE EQ LIMIT/DAY execution, and registered individual-app browser consent. Phase 6 advanced reads and phase 7 additional products remain planned; the complete method map records delivered, equivalent, internal/replaced and deferred behavior individually. Existing SDK reads/portfolio services were reused rather than duplicated.

The official public compact master downloaded and validated during development contained 17,269 unit-lot NSE/BSE equity records. This verifies the importer against actual public metadata, not any account/feed entitlement. Original tick units are retained. Public metadata imports are super-admin controlled and preserve existing instrument IDs.

Current changes are documented by module in DHAN_INTEGRATION_GUIDE.md. Added schema revision 0010 stores encrypted, one-use owner/session-bound consent attempts with tenant RLS. Existing source and all public domains remain GNK Algo. There is no migration to a new application stack or reference project deployment.

Verification: full backend suite passed locally (200 passed, 15 platform/PostgreSQL skips); TypeScript/Vite build passed; a populated old database upgraded to head with ORM/schema equality and preserved legacy account data. Existing account/research screens passed actual local API plus mocked-broker browser checks at 1440/768/390 px, without order writes. New private feed, consent and execution controls have additional mocked integration/browser coverage. Real broker acceptance and the production ARM build remain deployment-environment checks.

Production live flags and secrets were not changed. A successful code test does not establish broker permission, feed availability, or authorization to submit an account's real orders. The Dhan execution switch is new and independently configured; existing Upstox behavior is preserved.
