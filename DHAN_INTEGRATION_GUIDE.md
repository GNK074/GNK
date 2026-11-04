# GNK Algo — Dhan integration API and deployment

## Current implementation

The assessment and complete SDK mapping are in DHAN_TECHNICAL_ASSESSMENT.md and docs/dhan-sdk-feature-map.json. This release extends GNK rather than replacing its frontend, authentication, database or execution ledger. Installed SDK: `dhanhq==2.3.0`; reference revision `8c6583e6e169fd0293e2271cb5fcb5aad3f8e805`.

Implemented additions: bounded Indian equity master import; personal live quote/order notifications; registered individual-application consent; Dhan dispatch through existing durable intents, risk checks, explicit account arming, cancellation and REST fill reconciliation. Existing portfolio, renewal, option-chain, historical/chart and trade-history services remain available. Existing Upstox/global live settings are preserved. No live order was sent during development.

This is not all SDK products: modification/slicing, MARKET/SL variants, overnight/derivative trading, Super/Forever/Conditional orders, position conversion/liquidation, EDIS, broker-side P&L controls, margin/ledger/expired-option expansion, global stocks and 20/200-depth feeds remain roadmap work. GNK emergency stops block new submissions; they do not claim broker-side liquidation or cancellation.

## Screens and workflows

- `/user/dhan`: existing account, market snapshots, expiry/option-chain, historical research and trade-history tabs; new private live-feed tab. A super administrator can synchronize the public master. Browser consent appears only when configured.
- `/user/portfolio`: existing owned cross-broker snapshots and refresh/backoff logic.
- `/user/live-orders`: choose Dhan or Upstox; select broker-specific instruments; use the existing account/strategy approval, review/confirmation and order ledger. For Dhan, connect the selected instrument's private feed first. All open positions must have a broker-reported last price or a fresh subscribed quote before exposure checks can pass.
- `/tradedetails/orders`, `/tradedetails/client-trade-history`, `/tradedetails/signals`: existing GNK reporting consumes the same order/fill ledger. Notifications alone never create fills or realized P&L.

Personal feed subscriptions expire after 600 seconds unless refreshed, and also require a valid GNK login session/access token. The UI refreshes while open; an expired login closes its socket and requires reconnecting. Disconnected prices are explicitly stale. Maximum 100 watched instruments/account, 32 managed accounts/worker and 3 browser sockets/user are conservative GNK limits, not claims about broker entitlements. Multiple workers use Redis account leases to avoid duplicate upstream connections. Current UI watches one selected NSE equity at a time. A separate order socket remains for outstanding execution intents; REST reconciliation remains independent of the browser.

## Configuration

Append only new configuration names to your existing server environment; preserve encryption/database secrets, global trading flags and existing Upstox values.

```dotenv
DHAN_STREAM_ENABLED=true
DHAN_OAUTH_ENABLED=false
DHAN_EXECUTION_ENABLED=false
DHAN_EXECUTION_REFERENCE=
DHAN_TICK_SIZE_MULTIPLIER=0
DHAN_STREAM_WORKER_MEMORY_LIMIT=1g
```

These are new-feature defaults, not instructions to change your current global live-trading settings. Dhan placement requires `TRADING_ENABLED=true`, `LIVE_TRADING_ENABLED=true`, `DHAN_EXECUTION_ENABLED=true`, a real operator-reviewed `DHAN_EXECUTION_REFERENCE`, positive verified `DHAN_TICK_SIZE_MULTIPLIER`, enabled private streams and the registered `BROKER_EGRESS_IP`. It also requires current GNK broker approval evidence, administrator authorization of the owner/account/strategy, owner arming, worker readiness, fresh master/quote and all existing risk checks. Do not invent approval references. A reference string does not verify broker approval by itself.

The public master preserves original tick units. An observed master sample had raw tick sizes `5.0000` and `10.0000`; determine the permitted instrument's INR conversion from broker documentation and acceptance testing before configuring the multiplier. No default conversion is assumed. NSE equity intraday LIMIT/DAY, unit lots, no new short selling, weekday entry window 09:15–15:20 IST are the implemented execution scope; fresh exchange timestamps also prevent entry on inactive sessions.

For browser consent, register the exact HTTPS URL `https://gnkalgo.com/api/v1/dhan/oauth/callback` in the user's Dhan application before setting `DHAN_OAUTH_ENABLED=true`. The user supplies their own application credentials in GNK's form, then signs in on the broker website. GNK does not collect broker PIN/TOTP setup secrets. Temporary application credentials are encrypted, cleared before one-time exchange, and expired attempts are cleaned by the enabled stream worker. Cookie proof is session/user/account bound; reconnecting disarms and removes prior live authorization through the existing connector.

## API reference

All HTTP paths below use `/api/v1`. Existing login/MFA/disclosure policy applies. Mutations require the session's `X-CSRF-Token` and cookies. Broker tokens, application secrets and token IDs are never returned to the frontend. Live order mutations are never automatically retried.

Account/data endpoints retained:

- `GET /dhan/status`, `GET /dhan/profile?account_id=...`
- `POST /dhan/accounts/{id}/renew`
- `POST /dhan/quotes` with account_id, segment, security_ids and mode (ltp/ohlc/full)
- `GET /dhan/expiries`, `/dhan/option-chain`, `/dhan/history`, `/dhan/trade-history` with owner account and bounded parameters shown in `/docs`
- Existing `/portfolio/*` for normalized holdings, positions, funds, order/trade snapshots and synchronization status.

New metadata/feed/authentication endpoints:

- `GET /dhan/instruments?q=RELIANCE` returns up to 50 active NSE equity GNK instrument IDs in `DHAN|NSE_EQ|securityId` namespace; no broker credentials required for public metadata.
- `POST /dhan/instruments/sync` requires SUPER_ADMIN, downloads only the fixed official public master, validates it and atomically updates unit-lot NSE/BSE equity metadata. Old IDs remain stable; failed imports retain the previous master.
- `POST /dhan/stream/subscribe` with `{"account_id":"owned-account","instrument_ids":["gnk-instrument-id"]}` returns `{"subscribed":1,"expires_in":600,"refresh_before_seconds":120,...}`. Empty list stops that account's browser watch. Only active Dhan metadata is accepted.
- `POST /dhan/stream-ticket` with `{"account_id":"owned-account"}` returns a one-use, 30-second GNK ticket. Open `/ws/v1/dhan` using subprotocols `["gnk.dhan", ticket]`; the allowed Origin must match the configured frontend. Do not put broker tokens or GNK tickets into query strings.
- WebSocket message: `{"type":"broker_update","ticks":[{"instrument_key":"DHAN|NSE_EQ|1330","ltp":"100.25","data_status":"LIVE","exchange_timestamp":1793850300,...}],"order_update":null,"connection":{"market_connected":"1","order_connected":"1"}}`. `UNAVAILABLE` and `STALE` are explicit states; no stale quote authorizes placement.
- `POST /dhan/oauth/start` with client_id, app_id, app_secret, owns_account:true, terms_accepted:true sets a private signed consent cookie and returns a fixed broker authorization URL. `GET /dhan/oauth/callback?tokenId=...` consumes the cookie/attempt once, verifies the returned identity through the existing connector and redirects to `/user/dhan?oauth=connected` or `failed`. Broker token exchange is not retried.

Existing execution APIs extended, not duplicated:

- `GET /live/readiness?broker=dhan`
- `POST /live/accounts/{id}/arm` with `{"confirmation":"ENABLE LIVE DHAN"}`; disarm remains `/disarm`.
- `POST /live/orders` uses the existing schema, e.g. broker_account_id, strategy_id, instrument_id, symbol, side:BUY, quantity:1, price:"100.00", a unique idempotency_key and confirm_real_money:true. It creates a durable GNK intent before contacting the broker. Returned PENDING is not a fill; UNKNOWN requires reconciliation and blocks replacement.
- `GET /live/orders`, `GET /live/positions/{id}`, `POST /live/orders/{id}/reconcile`, `/cancel` retain owner checks. Cancellation is available when new placement is stopped, but needs a verified broker order identity.
- Existing super-admin broker approval and `/admin/live/accounts/{id}/authorization` now accept the Dhan adapter. All 18 current evidence checks still apply.

Typical errors: 401 invalid/expired GNK session; 403 CSRF/role/ownership permission; 404 foreign account/instrument; 409 provider session, approval/risk/stale-feed/operational blocker; 422 invalid fields; 429 distributed request limits. SDK/provider failures return sanitized codes, not raw response bodies. Check `/docs` and `/openapi.json` for generated schemas.

## Production deployment

No production server changes were made by this development session. Run on the Oracle VM after pulling this release:

```bash
cd /opt/gnk
git pull --ff-only
export GNK_ENV=production
# Keep your existing valid GNK_BACKUP_RECIPIENT and local public encryption key.
./deploy/redeploy_dhan.sh
```

The script verifies secret-file permissions, starts Postgres/Redis, builds all application workers including `dhan-stream-worker`, takes the configured encrypted backup, provisions runtime grants, migrates to `0010`, recreates application services, recreates Nginx after upstream addresses change, then validates schema/Redis/environment and HTTP health. It does not edit `.env` or activate trading. Backup failure stops deployment before migration. Migration requires the migration role; application credentials never perform DDL.

There are now ten Compose services including both portfolio and Dhan stream workers. Worker health indicates process/cache heartbeat, not broker authentication or a fresh feed. Confirm account/feed status in GNK separately.

```bash
GNK_ENV=production ./deploy/gnk-service.sh status
GNK_ENV=production ./deploy/gnk-service.sh health
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  logs --since 10m --tail 80 dhan-stream-worker portfolio-worker execution-worker backend
```

After deployment: synchronize the master as super admin; connect your owned Dhan account; refresh/compare portfolio records with the broker; verify historical/option reads; connect a private feed and observe fresh/stale/disconnect behavior. Review production evidence/configuration before separately authorizing live placement. Do not use a real order as a health probe. Preserve existing broker orders and reconcile any outstanding intents during upgrades. Rollback across schema revisions requires a reviewed restore/forward-fix; the consent migration intentionally refuses destructive downgrade.

## Verification and limits

Automated tests use fake broker HTTP/socket transports, SQLite integration sessions and fake Redis. They cover read-only default transport, capability-scoped writes, ambiguous responses without retries, durable idempotency, broker/provider mismatch, sanitized order normalization, account isolation, CSRF, one-use stream tickets, Origin/revocation, fresh/stale leases, encrypted replay-safe consent, privileged metadata sync and expired sessions. Existing Upstox, account, portfolio and risk suites remain required.

Local migration verification upgraded a populated old schema to `0010`, preserved legacy account data and matched ORM metadata. PostgreSQL-specific tenant isolation tests now include consent attempts and run in the existing isolated PostgreSQL CI job; this Windows host has no local PostgreSQL service. Frontend build and responsive mocked-browser checks are required before release. Actual broker permissions, ARM Docker build, public callback registration and production account acceptance must be verified on the deployment environment; they are not established by unit tests.
