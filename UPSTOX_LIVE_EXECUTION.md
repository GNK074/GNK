# Upstox live-execution implementation and activation

This release adds a controlled real-order path. It is implemented and tested offline, not activated on the Oracle server. No real broker order, cancellation or funds movement was performed during development.

## Supported scope

Upstox individual trading accounts; active, recently synchronized NSE EQ instruments with lot size 1; intraday product I; LIMIT/DAY orders; BUY and SELL of unreserved existing intraday long positions. No short selling, market orders, derivatives, delivery/MTF, AMO, slicing, order modification, automated strategy scheduling, auto-liquidation or automatic replacement/retry of uncertain submissions.

Live and paper ledgers are separate. The broker's actual positions and trades are authoritative; an HTTP order acknowledgement is never recorded as a fill. Live ledger fills are reconciled from broker order/trade responses. Paper positions are never updated by a live response.

## Submission and protection

- Existing session, MFA and CSRF authentication, disclosure acknowledgment and explicit real-money order confirmation.
- Global server activation; current evidence for all existing 18 broker requirements; super-admin production approval; account authorization; approved strategy; user account arming.
- Platform, account and personal stops. Clearing a stop does not clear any other gate. Stopping placement does not cancel orders already sent or close positions.
- Owned encrypted individual trading credentials with current expiry and broker identity check. The market-data Analytics Token is never used for execution.
- Fresh LIVE market quote, configured price-deviation band, verified tick-size scaling and recently synchronized instrument master.
- Quantity, order value, projected position quantity/value, portfolio exposure, daily orders and broker realized/unrealized account loss. External broker positions and pending orders contribute to checks; manual trading elsewhere can still race an application preflight and must be controlled operationally.
- A durable SUBMITTING intent is committed before broker submission. User/account locks serialize submissions; permissions and stops are reloaded before submission. The API uses caller idempotency keys and unique broker tags. A request with the same key returns its prior intent; another payload with that key is rejected.
- Network timeout, ambiguous response or process death leaves the intent uncertain. The application never automatically resubmits it. Uncertain intents block new account submissions until reconciled. Tags support matching, not an assumption that Upstox guarantees exactly-once execution.
- Reconciliation validates tag, broker ID, instrument, product, side, quantity and limit price. Fill sums must match broker filled quantity; quantities do not regress and terminal states cannot regress. Broker responses are sanitized and tokens never logged.
- Cancellation remains available when placement is disabled or a kill switch is set. A cancellation response means requested cancellation, not a confirmed cancelled order.

## Added API

- POST /api/v1/live/orders — guarded real submission (existing route now implemented).
- GET /api/v1/live/readiness — server, broker and reconciliation readiness plus owned Upstox account authorization/arming.
- GET /api/v1/live/orders — owned live ledger, separate from paper orders.
- GET /api/v1/live/positions/{account_id} — current owned broker positions.
- POST /api/v1/live/accounts/{account_id}/arm — explicit ENABLE LIVE UPSTOX confirmation.
- POST /api/v1/live/accounts/{account_id}/disarm — stops new placement, no automatic liquidation.
- POST /api/v1/live/orders/{order_id}/reconcile and /cancel — owned order controls.
- PUT /api/v1/admin/live/accounts/{account_id}/authorization — super-admin grant/revoke; user_id, enabled and owned strategy_ids. Always disarms the account.
- Existing /api/v1/admin/brokers/upstox/production-approval now permits approval only with current evidence, explicit server activation and healthy reconciliation.

User screen: /user/live-orders. Administration reuses the broker evidence review and adds account/strategy authorization plus platform-stop controls. The order form reviews account, instrument, side, quantity, price and notional before a distinct real submission action.

## Deployment — keep live placement off initially

Make this committed source available to the VM's deployment branch first. From /opt/gnk, configure the existing encrypted-backup GPG recipient in the shell (the real public-key fingerprint, not an SSH key). Keep LIVE_TRADING_ENABLED=false, TRADING_ENABLED=false and UPSTOX_EXECUTION_ENABLED=false for the initial schema deployment.

```bash
cd /opt/gnk
git pull --ff-only
export GNK_BACKUP_RECIPIENT='YOUR_EXISTING_GPG_PUBLIC_KEY_FINGERPRINT'
GNK_ENV=production ./deploy/deploy_production.sh
GNK_ENV=production ./deploy/gnk-service.sh health
```

Migration 0007 follows 0006 and adds only live_orders, with tenant RLS and composite account/strategy ownership constraints. It preserves existing users, secrets, market data and paper records. The updated migration script verifies the committed schema through a fresh connection. Do not stamp revisions manually or delete volumes. New Compose service execution-worker polls and reconciles orders; it never creates, replaces or retries an order.

## Activation after operational acceptance

The following entries are required in the VM environment. The references, IP and scaling values must be actual reviewed deployment values; do not paste placeholders as live configuration. All sample env files remain disabled. MARKETDATA_APPROVAL_REFERENCE=false is now rejected when distribution is marked approved; use the actual reviewed reference or leave distribution disabled.

```dotenv
APP_ENV=production
ENVIRONMENT=production
TRADING_ENABLED=true
LIVE_TRADING_ENABLED=true
UPSTOX_EXECUTION_ENABLED=true
LIVE_EXECUTION_REFERENCE=actual-reviewed-execution-release-reference
BROKER_EGRESS_IP=actual-static-public-egress-IP-registered-with-Upstox
LIVE_PRICE_DEVIATION_PERCENT=2
LIVE_TICK_SIZE_MULTIPLIER=verified-conversion-from-provider-tick-size-to-INR
# If applicable, exactly the exchange-approved name registered for this app:
UPSTOX_ALGO_NAME=
```

LIVE_TICK_SIZE_MULTIPLIER must be numeric and positive. Its default 0 deliberately prevents live activation until units are verified. The instrument master retains original provider values. For example, if a reviewed provider value of 5 is confirmed to mean INR 0.05, the multiplier is 0.01; that example is not verification of every instrument. Live activation also rejects missing/placeholder execution references and non-public egress IPs.

Keep existing JWT, SECRET_KEY, field-encryption keys, database and Redis secrets unchanged. Replace the SMTP app password previously exposed in chat using the provider's account controls; do not put any new password in chat or Git.

After server configuration is valid:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  up -d --no-deps --force-recreate --wait --wait-timeout 180 \
  backend market-worker execution-worker
./deploy/validate_environment.sh
GNK_ENV=production ./deploy/gnk-service.sh health
```

Then:

1. Connect the owner's Upstox account through Brokers & exchanges using its individual trading access token. The separate Analytics Token remains read-only. Account authorization is reset on reconnect.
2. Complete broker requirements with actual current evidence, including registered-app/API permissions, static IP, execution, reconciliation, risk, emergency stop and operational monitoring. Evidence recording is an administrator attestation; the application does not independently validate the external evidence document. Run sandbox/production-equivalent acceptance before approving the production scope.
3. As super-admin, run the Upstox production approval gate. Other brokers remain unsupported for live execution.
4. Create a strategy if needed in the existing strategy workspace. In Administration authorize the user's Upstox account and the specific strategy IDs. The account remains disarmed.
5. Configure conservative personal risk limits. Clear the platform stop explicitly only when ready; clear the personal stop if set. In Live orders select the account and type ENABLE LIVE UPSTOX to arm it.
6. Market-data approval, token, entitlement, instrument synchronization and upstream LIVE feed must already work. A stale, snapshot-only, unknown-session or disconnected quote cannot authorize submission.
7. Review the real order screen. Each order requires its own confirmation; no order is automatically generated merely by enabling an account or flags. An uncertain order must be investigated/reconciled, not replaced with a new key.

## Rollback and operation

Set LIVE_TRADING_ENABLED=false and TRADING_ENABLED=false and recreate backend to block new placement. Disarm accounts or set the global emergency stop for immediate application-side blocking. An in-flight broker request may already have been accepted. Leave execution-worker running to reconcile existing orders, and manage open orders/positions through the application cancel controls or the broker. There is no claim of automatic liquidation or cancellation on shutdown. Expired/disconnected credentials and previous-day orders no longer present in the broker day book require operator/broker review; uncertain intents are not automatically cleared.

## Verification and remaining acceptance

- Backend regression suite: 118 passed, 15 skipped before final documentation; includes 13 new Upstox tests for durable intents, idempotency, uncertain timeouts/no resubmission, stops, ownership/CSRF, price/tick/quantity/loss checks, partial/final fills, unknown recovery, cancel while disabled, credential expiry, worker reconciliation while placement is disabled, malformed fills, permission revocation and explicit configuration.
- Final focused Upstox execution suite: 14 passed, including an additional successful V3 submission/cancellation transport contract test. All broker responses in these tests are mocked.
- Populated SQLite 0001 → 0007 migration and ORM comparison passed; legacy password preserved. Existing migration/security tests remain passing.
- TypeScript/Vite production build passed. Headless Chromium at 1440, 768 and 390 pixels passed order review/confirmation, uncertain ledger rendering and admin-control checks with mocked APIs; no page exceptions or page overflow.
- Isolated PostgreSQL RLS test now also checks the live ledger and cross-user updates; Linux/PostgreSQL-dependent checks remain CI-only here.
- No local Docker runtime is available, so actual container boot, live Upstox API permission/static-IP behavior, order placement/cancellation/fills, broker rate limits under load and recovery/soak acceptance must be verified before production activation. The code does not establish that operational approval has occurred.
- No public deployment or real trade was performed by this development session.

## Official contracts consulted

[Upstox V3 order submission](https://upstox.com/developer/api-documentation/v3/place-order/), [V3 cancellation](https://upstox.com/developer/api-documentation/v3/cancel-order/), [order book](https://upstox.com/developer/api-documentation/get-order-book/), [order trades](https://upstox.com/developer/api-documentation/get-trades-by-order/), [positions](https://upstox.com/developer/api-documentation/get-positions/), [instruments](https://upstox.com/developer/api-documentation/instruments/) and [rate limits](https://upstox.com/developer/api-documentation/rate-limiting/).

## Migration configuration isolation

The migrator explicitly overrides trading, Upstox execution, upstream streaming/history and distribution activation flags to false. This lets schema maintenance and post-migration verification run while a live rollout has incomplete activation settings. Production database credentials, encryption, MFA/HTTPS requirements and runtime validation remain unchanged. Backend and worker services still require valid runtime configuration; migration success does not activate live orders.

Regression checks: migration environment and existing security configuration tests pass (5 tests), including incomplete runtime live activation and a placeholder market-data approval reference.
