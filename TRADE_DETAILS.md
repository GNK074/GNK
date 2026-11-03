# Trade details: Orders, Trade History and Signals

## Implemented

- Broker connection success text: **Broker & Exchange settings created successfully!** A saved individual connection shows the exact message in a persistent status panel and notification. OAuth callback success is shown after refreshing the user's actual connected accounts. A failed connection does not generate this success message.
- /tradedetails/orders — ACTIVE, PENDING, CLOSED, FAILED and Show All tabs; owner-scoped Broker, Script, Group Service and Search filters; sortable columns, server pagination, running gross P&L, record details and the existing personal kill switch.
- /tradedetails/client-trade-history — From/To dates in India Standard Time, broker/strategy/script/status/search filters, sortable history, gross realized P&L, entry/exit quantities and prices, response/state, Trade View and a real XLSX Excel export of all matching records, not just the visible page.
- /tradedetails/signals — stored signals, symbol/type/side search, sorting, pagination, empty state, detailed view and manual signal creation. Creating a manual signal only saves a record; it never submits a broker order.
- Orders navigation now opens /tradedetails/orders. The existing real-order entry form remains available at /user/live-orders through the **Place order** button. History and Signals also have sidebar navigation and shared tabs.
- The existing application shell, authentication, themes and responsive layout are reused. Tables scroll internally on small screens.

## Field meanings and scope

These pages report the signed-in user's recorded **live** execution data. Other clients' records are never included, including for administrator users. Existing paper trading records and routes are unchanged. Broker filters list the user's broker accounts; they do not imply that an unsupported broker can execute orders. Group Service uses the existing strategy name. Script uses the synchronized underlying/symbol; the five requested index labels are filter choices and do not create instruments, prices or trades.

SL and TP columns show **—** because the existing execution ledger has no protective-order fields. This release does not create stop-loss or take-profit broker orders. Missing values remain unknown; they are not replaced with zero or demo data.

Order tabs describe execution status: OPEN → ACTIVE; submitting/pending/cancel-pending/uncertain → PENDING; filled/cancelled → CLOSED; rejected → FAILED. A filled buy order may still represent an open position. Trade history additionally labels the tracked fill lifecycle as OPEN, PARTIALLY_CLOSED, CLOSED, UNKNOWN or NO_FILL.

P&L uses exact Decimal arithmetic and FIFO matching of reconciled fill events within each broker account, instrument and product. It excludes brokerage, taxes, fees and corporate-action adjustments. Matching does not cross accounts. Entry Group Service is the entry order's strategy. Signal timestamps on historical orders are recorded order-intent times, distinct from exchange fill timestamps.

Missing or invalid fill timestamps, duplicate fill IDs or absent entry basis produce unknown P&L. External/manual broker trades that were not recorded by GNK are not invented or imported. Unmatched exits remain visible with unknown entry price and P&L. Unfilled/rejected requests remain visible as NO_FILL records. Partial exits preserve the remaining FIFO lot cost rather than incorrectly using the original average cost.

Running P&L uses only authorized cached prices labelled LIVE. Disconnected, stale, missing, unapproved and snapshot-only prices do not produce running P&L. Price cells retain their data-status labels. A partial pricing set shows an unknown total and its coverage count. No report fetch calls a broker order endpoint or auto-refreshes/replays an order submission.

The kill switch activates the existing personal order stop. It does not change global live-enablement settings, cancel working broker orders or liquidate positions.

## API and data

All endpoints require the existing authenticated, MFA-complete session. Mutations require CSRF. New endpoints under /api/v1/tradedetails:

- GET options — owned broker accounts/strategies and Script filter choices.
- GET orders — bucket, broker, script, strategy_id, q, status, from_date, to_date, page, page_size, sort and direction.
- GET orders/{order_id} — owned order details and related tracked history.
- GET client-trade-history — the same applicable filters, sorting and pagination.
- GET client-trade-history/export — XLSX of the filtered owner-scoped history.
- GET signals — q, page, page_size, sort and direction.
- GET signals/{signal_id} — owned signal details.
- POST signals — strategy_id, optional owned account_id, instrument_id, side, quantity, order_type, optional reference_price and note. Instrument access requires the user's existing market-data entitlement. Arbitrary user IDs or source order IDs cannot be submitted.

List page size is 10 by default, capped at 100. Reports process at most 10,000 recorded orders per owner; larger ledgers require a reviewed archive/reporting extension. Filters run after FIFO reconstruction so a date filter does not silently discard the entry cost basis needed for an exit.

Excel output uses explicit string cells for text, preventing formula execution from names or other text beginning with =. Numeric values retain numeric cell types. Export and detail endpoints enforce the same ownership rules as the lists; no credential ciphertext or token is serialized.

## Migration 0008

- Adds trade_signals with user RLS and composite ownership constraints for linked strategy, broker account and source order.
- Adds a redundant id/user ownership key to live_orders to support the composite source-order foreign key.
- Backfills one ORDER_REQUEST signal per existing recorded live-order intent using its actual timestamp and stored instrument data. These records are explicitly requests, not broker fills or AI-generated recommendations.
- New order intents save the corresponding signal in the same transaction. Retrying an existing order idempotency key does not create another signal or broker order.
- Preserves all existing users, orders, fills, broker credentials and market data. Destructive downgrade is refused; use a reviewed forward migration.

## Verification

- Full backend suite: 142 passed, 15 skipped (Linux/PostgreSQL-specific checks require CI).
- Focused reporting/migration suite: 9 passed, including owner isolation, filters, pagination, sorting, FIFO partial/complete exits, unknown basis, credential-free output, signal-only persistence, idempotent order signals and filtered XLSX export.
- Populated 0001 → 0008 migration and ORM comparison passed. A separate populated 0007 → 0008 test verifies backfill and repeat-upgrade behavior without changing the original order state.
- PostgreSQL CI isolation test extended for signal RLS and cross-owner source-order constraints; not run against a local PostgreSQL instance here.
- TypeScript/Vite production build passed.
- Headless Chromium against local API/database fixtures passed Orders filtering/sorting/pagination/detail, personal kill switch, filtered history and Excel download, persisted manual signals/details, the exact broker-success message, and all three pages at 1440/768/390-pixel widths. No page exceptions, horizontal page overflow or live-order submission occurred. Broker identity verification used a local fake profile verifier; no real account was connected.
- Browser-downloaded XLSX opened in an independent spreadsheet reader with the expected filtered row count. Formula-like text was independently verified to remain a text cell.

## Production deployment

Once the commit is available on the VM, deploy the matching schema and all Python service images together. Keep the current .env and live-trading settings unchanged. Do not regenerate credentials, clear volumes or manually stamp a migration revision.

Use the existing GPG backup recipient in the same shell. The following sequence explicitly recreates Nginx after backend/frontend addresses change:

```bash
cd /opt/gnk
(
  set -e
  git pull --ff-only
  dc=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
  ./deploy/check_secret_permissions.sh
  "${dc[@]}" up -d --wait postgres redis
  "${dc[@]}" build backend frontend market-worker execution-worker
  ./deploy/backup_database.sh
  ./deploy/provision_database_role.sh
  ./deploy/migrate_database.sh
  "${dc[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 180 \
    backend frontend market-worker execution-worker
  "${dc[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 60 nginx
  ./deploy/validate_environment.sh
  GNK_ENV=production ./deploy/gnk-service.sh health
)
```

The migrator isolates schema maintenance from execution activation flags; it does not disable the runtime services' configured live flags. If a step fails, stop and inspect that step's output before starting services. After deployment, sign in and open the three new routes, verify filters/export with your own data, and confirm the broker-success message after an authorized account connection.

This development session did not deploy to the Oracle VM, alter production settings or place real orders.
