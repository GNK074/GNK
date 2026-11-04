# Unified broker portfolio

The `/user/portfolio` page now displays read-only, owner-scoped broker snapshots instead of the paper-order workspace. Paper trading remains on Strategies. Runtime live-trading settings and execution gates are not changed.

## Implemented behavior

- Overview cards separate holdings investment/current value/P&L from position realized/unrealized P&L. No combined net-worth or pooled-cash total is invented.
- Holdings, Positions, Funds & margins, Orders & trades, and Broker accounts tabs. Broker books are separate from GNK-recorded Orders and Trade History.
- Account/broker/exchange/product/asset/symbol filters, server-side pagination and sorting, detailed snapshot views, and owner-filtered native XLSX export. Exports contain underlying account rows, even when the UI consolidates holdings.
- Optional consolidation merges only eligible equity holdings with the same verified ISIN and INR settlement, keeping all underlying account rows. Other products, unknown identifiers and positions stay separate. Equity classification must come from a broker instrument-type field or a matching active EQ instrument-master record; an INE prefix alone does not establish asset class. Consolidated prices are weighted snapshot valuations, not executable quotes.
- Prices are labelled broker snapshots. Missing values remain null/—. A summary total is withheld if required accounts/values are missing or stale; the API separately identifies known subtotals and coverage.
- Disconnected accounts retain their historical snapshots as stale. After credential replacement, old-credential snapshots are hidden until new data arrives. Expired sessions link to Brokers & exchanges for reauthorization.

## Broker capability matrix

All six adapters implement read-only holdings, net positions, funds/margins, current order book and current trade book. This means implementation and fixture coverage, not successful verification against each customer's live account. The existing broker connector verifies identity; this service reuses its encrypted owner-bound session and expiry.

- **Upstox:** v2 holdings, net positions, equity/commodity margin ledgers and daily order/trade books. Funds service availability and returned fields depend on the provider's service window and API version. [Portfolio](https://upstox.com/developer/api-documentation/get-holdings/), [positions](https://upstox.com/developer/api-documentation/get-positions/), [funds](https://upstox.com/developer/api-documentation/get-user-fund-margin/).
- **Dhan:** v2 holdings/positions, fundlimit, orders and trades. Broker-reported realized/unrealized values are retained; absent prices stay unknown. [Portfolio](https://dhanhq.co/docs/v2/portfolio/), [funds](https://dhanhq.co/docs/v2/funds/).
- **Zerodha:** Kite Connect holdings, net positions (not both net and day arrays), margin ledgers and daily books. T1 quantities follow the published holdings contract. [Portfolio](https://www.kite.trade/docs/connect/v3/portfolio/), [user/margins](https://www.kite.trade/docs/connect/v3/user/).
- **Angel One:** SmartAPI holdings, positions, RMS and books. Existing API key/JWT and configured server egress identity are required. [Official SDK routes](https://github.com/angel-one/smartapi-python/blob/main/SmartApi/smartConnect.py).
- **FYERS:** v3 holdings, netPositions, fund_limit, orderBook and tradeBook. Holdings use remainingQuantity; funds use the Available Balance heading, with capital/commodity separate. Transactions Info permissions are required. [Holdings](https://fyers.in/api-docs/v3/api/account/holdings/), [funds](https://fyers.in/api-docs/v3/api/account/funds/), [positions](https://fyers.in/api-docs/v3/api/trading/positions/).
- **5paisa:** V3/Holding, V3/NetPositionNetWise, V4/Margin, V4/OrderBook and V1/TradeBook. These documented POST endpoints only read account data. NetAvailableMargin is not treated as withdrawable cash; fields with unclear P&L basis remain unknown. No cross-broker merging is attempted without a returned ISIN. [Holdings](https://xstream.5paisa.com/dev-docs/portfolio-management-system/holdings), [positions](https://xstream.5paisa.com/dev-docs/portfolio-management-system/netwise-positions), [margin](https://xstream.5paisa.com/dev-docs/funds-management-system/margin), [trade book](https://xstream.5paisa.com/dev-docs/order-tracking-system/trade-book).
- **Other brokers:** shown as Unsupported; connection authentication alone does not imply a portfolio adapter exists.

Official references reviewed on 4 November 2026. Provider permissions, subscriptions, availability and customer authorization still govern successful reads. No live credentials were used in development. This release does not implement long-range broker reporting, mutual-fund-specific APIs, MTF-specific books, tax lots, corporate-action adjustments or transaction-based cost reconstruction. Asset types without a verified classification remain UNKNOWN; positions are not merged by symbol.

## Storage and synchronization

Migration **0009**, following 0008, creates `portfolio_snapshots` (one latest complete endpoint snapshot per account/kind) and `portfolio_sync_states`. Both use tenant RLS and composite account-owner foreign keys. No existing orders, trading flags, account passwords or broker credentials are rewritten.

The new **portfolio-worker** discovers active/verified users, enters explicit tenant context and processes supported connected accounts. Browser GET requests never call broker APIs. Manual refresh queues work with a 30-second account cooldown; normal successful synchronization is due after 60 seconds. The worker processes due accounts sequentially. Large installations should monitor cycle latency before scaling replicas.

Each account uses a fenced Redis lease; endpoint snapshots are validated and atomically replaced individually. Credential-version and connection checks prevent publishing results after a credential change/disconnection. An account failure does not erase previous snapshots or prevent processing another account. Backoff grows to 15 minutes; manual refresh does not defeat broker backoff. A 180-second snapshot age marks it stale. Polling is every 15 seconds; this is not a streaming quote service.

Every adapter has fixed read endpoints, TLS verification, no redirects, bounded response size/row count, timeouts, and sequential reads spaced at least 1.1 seconds apart per account. Only network/server failures receive one bounded retry. Authentication, permission and rate-limit failures are not immediately retried. No order-placement/modify/cancel/exit endpoint is exposed by an adapter.

Only normalized allowlisted financial fields are stored. Credentials remain in the existing encrypted store. API responses/logs omit tokens and raw broker errors. Snapshot values use Decimal calculations and decimal strings in JSON. Funds stay per account/segment; instrument filters do not apply to funds. XLSX text cells cannot become formulas.

## API contracts

All paths require the existing authenticated session. POST additionally requires the existing CSRF proof.

- `GET /api/v1/portfolio/summary`: filtered holdings and position metrics, explicit completeness and account coverage.
- `GET /api/v1/portfolio/accounts` and `/sync-status`: owned accounts, capability flags, state, safe error codes, oldest full-coverage timestamp and reauthorization link.
- `GET /api/v1/portfolio/{holdings|positions|funds|orders|trades}`: items, coverage, pagination and provenance.
- `GET /api/v1/portfolio/{kind}/export`: filtered underlying account rows as XLSX.
- `POST /api/v1/portfolio/refresh`: `{ "account_id": "optional owned account ID" }`, or `{}` for all owned accounts; returns HTTP 202 with queued/unavailable account IDs and cooldown. This schedules reads only.

List filters: `account_id`, `broker`, `exchange`, `product`, `asset_class`, `q`. Page size 1–100. Sort keys are allowlisted. `consolidated=true` applies to holdings. UTC storage, Asia/Kolkata display.

## Production deployment

Commit/push this release first. In the Oracle VM shell, retain the existing `.env`, secrets and exported `GNK_BACKUP_RECIPIENT` fingerprint. Run:

```bash
cd /opt/gnk
(
  set -e
  git pull --ff-only
  dc=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
  ./deploy/check_secret_permissions.sh
  "${dc[@]}" up -d --wait postgres redis
  "${dc[@]}" build backend frontend market-worker execution-worker portfolio-worker
  ./deploy/backup_database.sh
  ./deploy/provision_database_role.sh
  ./deploy/migrate_database.sh
  "${dc[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 180 \
    backend frontend market-worker execution-worker portfolio-worker
  "${dc[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 60 nginx
  ./deploy/validate_environment.sh
  GNK_ENV=production ./deploy/gnk-service.sh health
)
```

Expect nine healthy services, including portfolio-worker. Sign in, open `/user/portfolio`, select your own broker account and request Refresh accounts. Verify provider permissions and reauthorize expired sessions through the existing connector. No test order is required to validate portfolio reads.

If deployment fails, stop at the failed step. Do not delete volumes or stamp migrations. For application rollback, preserve the encrypted backup and additive 0009 tables, stop portfolio-worker, and use a reviewed previous image/schema compatibility plan. Older releases enforce their own schema readiness, so blindly starting an older image against the new revision can fail. Do not perform an automatic database restore on a live trading system; a restore would lose newer account/order records and needs a coordinated maintenance/reconciliation plan.

This development session has not updated the Oracle VM.

## Verification results

- Full backend suite: **172 passed, 15 skipped**. Skipped checks require Linux or PostgreSQL CI infrastructure.
- Thirty dedicated portfolio cases cover owner isolation, CSRF, refresh throttling, per-account locks, credential replacement fencing, expired-session rejection, partial-response retention, exact financial calculations, missing/stale values, six broker holding/position/fund contracts, bounded transport retries, rate-limit handling, conservative asset classification, safe XLSX output and no created orders.
- Populated legacy schema upgrade through 0009 matched the ORM and preserved the legacy account/password. PostgreSQL CI isolation coverage now includes both portfolio tables; a local PostgreSQL run was not available.
- TypeScript/Vite production build passed.
- Headless Chromium against local API/database fixtures verified all six tabs at 1440/768/390-pixel widths; filtering, pagination, sorting, consolidation with details, account-filtered Excel download and queued refresh passed. No page errors, page overflow or order mutations occurred.
- The browser-downloaded XLSX opened with an independent spreadsheet reader and contained only the selected account's holdings row.
- Real customer broker authentication/permissions and provider response differences still require read-only verification after deployment; no customer tokens or real orders were used here.

## Dhan first-sync correction

A regression using the actual worker discovery loop and the published Dhan holdings shape reproduced an application failure: holdings with an ISIN but no asset type require a classification lookup. Adding an incomplete new snapshot before that lookup caused SQLAlchemy autoflush to insert it without required fields. Classification now finishes before the new snapshot is added; holdings, positions, funds, orders and trades can all be saved on the first sync. Missing broker prices remain unknown.

Unexpected account-sync exceptions now persist a safe error code and retry backoff, retain previous snapshots and appear in coverage/account status. Worker logs include only a fixed code, never exception text, SQL parameters, credentials or broker response bodies.

This correction changes no schema, broker credentials or execution flags. Update and rebuild backend and portfolio-worker, recreate those services, then recreate Nginx after the backend address changes. No additional migration beyond 0009 is needed.
