# Phase 05 — Market Data Engine

## Delivery status

Implemented for offline validation; production feed activation remains pending. No live Upstox connection, Oracle deployment, real exchange entitlement test or real-money order was performed. The user's confirmation that approval is available and response “upstock” identify the provider but do not establish the written redistribution scope. All sample configurations leave provider, streaming, historical fetching and distribution disabled.

## What was added

- Read-only provider interface and Upstox adapter. Analytics Token is separate from individual broker connections, encrypted using the existing field encryption system. Credentials and authorized WebSocket URLs never enter API responses or application logs.
- Official V3 Protobuf schema and generated decoder; authorized WSS host validation; binary subscription commands; bounded stream queue, reconnect with jitter and subscription restoration.
- One Redis-leased upstream manager across worker processes, compare-owner renewal/release and fenced cache/event writes. Duplicate and out-of-order provider/trade timestamps are rejected. Bounded Redis event stream and expiring latest quotes.
- JSON instrument import for NSE/BSE equity, futures, options and indices, including original instrument keys, strikes, expiry, lot size and tick size. Upserts preserve instrument IDs and candle references. Missing instruments become UNLISTED; expired/suspended records remain available for historical lookup.
- V3 historical/intraday synchronization with date chunking, UTC storage and original exchange timestamps. Supported intervals: 1/2/3/5/10/15/30 minutes, 1/2/4 hours, daily, weekly and monthly. Duplicate candles upsert; gaps are never interpolated.
- Durable bounded pending sync jobs, daily instrument scheduling, restart recovery, snapshot recovery and optional throttled latest-tick persistence. Default database tick persistence is off; expired snapshots are pruned.
- User entitlements, mode/segment permissions, expiry, personal/global capacity limits and PostgreSQL RLS for owned subscriptions/access. Worker context resets per transaction. Super-admin controls provider and access; ordinary admins may request synchronization.
- Authenticated API and one-use 30-second WebSocket tickets sent as subprotocols, avoiding URL tokens. Origin checks, session revocation/expiry rechecks, connection caps, message limits, slow-consumer resynchronization and mode-specific field filtering.
- Responsive market explorer, watchlist, full depth, option Greeks, stored-candle chart/table, pagination, provider/sync status and super-admin market controls in the existing application shell. REST snapshots, stale prices, disconnected prices and missing data are labelled; no demo prices are part of production UI.
- Market worker Compose service, Nginx WebSocket routing, Vite development proxy, service URL listing and CI test dependencies.

## Database migration

`0006` follows `0005` and creates eight tables: market_instruments, market_ticks_latest, market_candles, market_data_sync_jobs, market_data_provider_status, market_data_provider_secrets, market_data_entitlements, market_data_subscriptions. The six requested core models plus separate encrypted-secret and entitlement models are included. Migration downgrade deliberately refuses to delete history; use a reviewed forward migration. Existing accounts and broker/order data are preserved.

## HTTP and WebSocket contracts

All market HTTP endpoints require the existing authenticated session. Mutations require its CSRF token. Data access additionally requires configured distribution approval and a user entitlement.

Under `/api/v1/marketdata`:

- GET status, providers, health, sync-status
- GET instruments and instruments/search (filters and bounded pagination)
- GET instruments/{instrument_id}
- GET quotes?instrument_keys=KEY1,KEY2&mode=ltpc|full|option_greeks
- GET ohlc?instrument_keys=KEY1,KEY2
- GET history / intraday with instrument_id, interval, from_date, to_date, refresh, limit and before cursor
- GET / POST subscriptions; DELETE subscriptions/{subscription_id}
- POST ws-ticket

Under `/api/v1/admin/marketdata`:

- POST provider/enable and provider/disable (super-admin)
- POST instruments/sync and history/sync (admin)
- PUT users/{user_id}/access (super-admin): enabled, segments, modes, max_instruments, expires_at

Socket `/ws/v1/marketdata`: request a ticket through the authenticated CSRF-protected endpoint, connect with subprotocols `["gnk.marketdata", ticket]` and an allowed Origin. Commands use `action`, instrument_keys and mode: SUBSCRIBE, UNSUBSCRIBE, CHANGE_MODE, PING/PONG. Server messages: market_tick, subscription_ack, feed_status, resync_required, error, PONG. Tickets are consumed once; login access expiry and server session revocation are enforced. SUBSCRIBE/UNSUBSCRIBE update that user's stored watchlist.

## Verification performed

- Backend pytest: **105 passed, 15 skipped**. Skips require Linux Bash or isolated PostgreSQL; they are configured in existing CI jobs. New tests cover official Protobuf frames, malformed frames, numeric/time validation, singleton leasing, fenced writes, duplicates/order, ticket replay, socket caps, mode/tenant isolation, read-only endpoints, master/candle idempotence, missing quotes, invalid history and reconnect restoration.
- Populated SQLite migration 0001 → 0006: passed; legacy password preserved, prior security migration revokes old session, resulting ORM schema matches migration.
- TypeScript and Vite production build: passed.
- Headless Chromium browser checks at 1440 / 768 / 390 pixels: explorer selection, watchlist update, stored candle rendering and market-status route; no page exceptions or horizontal page overflow. These use isolated mocked API responses, not live prices.
- Added PostgreSQL RLS assertions to the isolated CI test. Not executed locally because no PostgreSQL/Docker runtime is available here.
- Existing trading/authentication/broker regression tests remain passing. No trading activation flags were changed.

## Deployment on the Oracle VM

After the code is available on your deployment branch, from `/opt/gnk`:

```bash
git pull --ff-only
# Keep all UPSTOX and distribution activation flags false initially.
GNK_ENV=production ./deploy/deploy_production.sh
GNK_ENV=production ./deploy/gnk-service.sh status
GNK_ENV=production ./deploy/gnk-service.sh health
GNK_ENV=production GNK_LOG_FOLLOW=0 ./deploy/gnk-service.sh logs market-worker backend
```

The production deploy script builds images, backs up the existing database, provisions runtime grants, rebuilds/runs the migration image, deploys and validates connectivity. Preserve existing database/Redis secrets and volumes. Do not regenerate secrets or use `down -v`. Review and add the `/ws/` location from `infrastructure/nginx/gnkalgo-https.example.conf` to your existing host TLS configuration without replacing certificates. Run `sudo nginx -t` before reload. Ensure the hostnames actually used by users (including www if applicable) are configured in the host proxy and the existing CORS allowed origins.

## Controlled activation after independent review

1. Record the actual written approval reference, permitted segments/modes, user limits, commercial redistribution and retention rights, and expiry. Restrict MARKETDATA_ALLOWED_SEGMENTS, MARKETDATA_ALLOWED_MODES, MARKETDATA_MAX_USERS and instrument limits to those terms. The sample six-segment list is a technical capability list, not permission.
2. Configure the dedicated read-only Analytics Token on the server. Prefer a mounted read-only secret file and UPSTOX_ANALYTICS_TOKEN_FILE pointing to it; add that mount to both backend and market-worker through a local untracked Compose override. The code also accepts UPSTOX_ANALYTICS_TOKEN in the server environment. Never put it in Git, browser storage or this chat. Existing FIELD_ENCRYPTION_KEY must remain available to decrypt the encrypted provider-secret row.
3. Enable UPSTOX_ENABLED and only the fetch capabilities covered by approval. Recreate backend and market-worker after configuration changes. In super-admin Administration, enable the provider (server-side authorization probe), request instrument sync and review Market status. Provider authorization alone does not authorize user distribution.
4. Only after terms are checked, set MARKETDATA_DISTRIBUTION_APPROVED=true and MARKETDATA_APPROVAL_REFERENCE to the reviewed reference, configure exact scope, recreate services, then grant individual user access with expiry. Leave UPSTOX_WEBSOCKET_ENABLED false until the upstream connection test is ready; enable it for the approved modes when ready.
5. Validate live ticks during an actual open session, REST snapshots during disconnection, subscription restoration after restart, invalid token/revocation, provider throttling and history against official provider responses. Verify exchange holiday/special-session settings and approved tick-size interpretation.
6. Confirm the public authenticated market-data health/status and Nginx upgrade path. Complete isolated PostgreSQL RLS CI and a production-equivalent container smoke test before declaring Phase 05 production acceptance.

## Known limits and remaining acceptance work

- No live provider token was used; all provider protocol and UI checks are offline fixtures. Exchange entitlements, actual Analytics Token behavior and production connection/load/soak tests remain unverified.
- V3 is used for streaming and candles; REST full quote snapshots intentionally use the documented read-only V2 quote endpoint. REST data is never labelled LIVE.
- Calendar fallback is explicitly SCHEDULED_OPEN/CLOSED, not official exchange confirmation. Only fresh ticks in a provider-reported NORMAL_OPEN segment can be LIVE. Low-liquidity instruments may become STALE despite a connected feed.
- Tick size is preserved in original provider units. No paise-to-rupee assumption is made; independently verify units before using it in an order-price calculation.
- A conservative global 1,000-instrument default (hard configurable maximum 1,500) and one upstream socket are used. Provider throttles are deliberately below documented aggregate limits. Queue overflow drops oldest queued ticks and records a counter; slow clients get fresh snapshots rather than an unbounded backlog.
- A single history job is capped at ten years and a REST page at 5,000 candles by default. Larger approved ranges require separate jobs/pages. Historical data remains raw provider candles; corporate-action adjustment is not invented.
- Existing strategy, AI, quant and risk placeholders are not connected to fabricated market data. `MarketDataService.require_live_quote` is the shared fail-closed consumption boundary; future executable consumers must explicitly use it. No order execution was added.
- Review the upstream schema's distribution/license conditions before any commercial packaging. The pinned official schema is included for protocol compatibility.

## Official protocol references

- [Analytics Token](https://upstox.com/developer/api-documentation/analytics-token/) — read-only capability does not establish redistribution rights.
- [V3 market data feed](https://upstox.com/developer/api-documentation/v3/get-market-data-feed/) and [authorization](https://upstox.com/developer/api-documentation/get-market-data-feed-authorize-v3/).
- [Official V3 Protobuf](https://assets.upstox.com/feed/market-data-feed/v3/MarketDataFeed.proto), SHA-256 `3e1c939dce2c83a3fef91405c5ca268dfa089aae973319f56685f12a5aFCF612` (case-insensitive).
- [Instrument master](https://upstox.com/developer/api-documentation/instruments/), [historical V3](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/), [intraday V3](https://upstox.com/developer/api-documentation/v3/get-intra-day-candle-data/).
- [Full quote REST](https://upstox.com/developer/api-documentation/get-full-market-quote/), [rate limits](https://upstox.com/developer/api-documentation/rate-limiting/).

## Changed and created files

- `.env.example` — updated
- `.env.production.example` — updated
- `.github/workflows/ci.yml` — updated
- `backend/app/database/tenancy.py` — updated
- `backend/app/main.py` — updated
- `backend/app/market_data/__init__.py` — updated
- `backend/requirements.txt` — updated
- `database/migrations/env.py` — updated
- `docker-compose.prod.yml` — updated
- `docker-compose.yml` — updated
- `frontend/src/layouts/App.tsx` — updated
- `frontend/vite.config.ts` — updated
- `infrastructure/nginx/default.conf` — updated
- `infrastructure/nginx/gnkalgo-https.example.conf` — updated
- `service/gnk-service.sh` — updated
- `tests/integration/test_postgres_rls.py` — updated
- `MARKET_DATA_PHASE05_REPORT.md` — created
- `backend/app/market_data/config.py` — created
- `backend/app/market_data/market_calendar.py` — created
- `backend/app/market_data/models.py` — created
- `backend/app/market_data/normalizer.py` — created
- `backend/app/market_data/persistence.py` — created
- `backend/app/market_data/provider_manager.py` — created
- `backend/app/market_data/providers/__init__.py` — created
- `backend/app/market_data/providers/base.py` — created
- `backend/app/market_data/providers/upstox/MarketDataFeed.proto` — created
- `backend/app/market_data/providers/upstox/MarketDataFeed_pb2.py` — created
- `backend/app/market_data/providers/upstox/__init__.py` — created
- `backend/app/market_data/providers/upstox/auth.py` — created
- `backend/app/market_data/providers/upstox/client.py` — created
- `backend/app/market_data/providers/upstox/historical.py` — created
- `backend/app/market_data/providers/upstox/instrument_master.py` — created
- `backend/app/market_data/providers/upstox/protobuf_decoder.py` — created
- `backend/app/market_data/providers/upstox/provider.py` — created
- `backend/app/market_data/providers/upstox/quotes.py` — created
- `backend/app/market_data/providers/upstox/websocket.py` — created
- `backend/app/market_data/redis_store.py` — created
- `backend/app/market_data/router.py` — created
- `backend/app/market_data/schemas.py` — created
- `backend/app/market_data/service.py` — created
- `backend/app/market_data/subscription_manager.py` — created
- `backend/app/market_data/tasks/__init__.py` — created
- `backend/app/market_data/tasks/historical_sync.py` — created
- `backend/app/market_data/tasks/instrument_sync.py` — created
- `backend/app/market_data/tasks/jobs.py` — created
- `backend/app/market_data/tasks/market_recovery.py` — created
- `backend/app/market_data/websocket_manager.py` — created
- `backend/app/market_data/worker.py` — created
- `database/migrations/versions/0006_market_data.py` — created
- `frontend/src/admin/MarketDataAdmin.tsx` — created
- `frontend/src/markets/MarketsPage.tsx` — created
- `frontend/src/markets/markets.css` — created
- `tests/integration/test_market_data_api.py` — created
- `tests/requirements.txt` — created
- `tests/unit/test_market_data.py` — created
- `README.md` — updated with Phase 05 documentation link.
