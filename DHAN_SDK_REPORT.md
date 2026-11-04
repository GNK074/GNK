# Official DhanHQ SDK integration — implementation and deployment report

## Release scope

This is an incremental SDK account/data/research release. It is **not completion of all eighteen phases** in the supplied master prompt. Existing real-money Upstox execution remains under its current settings and gates. This release does not activate Dhan order placement, cancellation, modification, automatic exits, streaming feeds or ML-generated trading.

## Repository analysis and architecture

The existing frontend is React 19/TypeScript/Vite, not Next.js. The backend is FastAPI with SQLAlchemy, PostgreSQL tenant RLS, encrypted owner-bound broker credentials, Redis and Docker Compose. The current deployment uses its existing FRONTEND_URL/public reverse proxy; no app.gnkalgo.com domain migration is introduced.

Before this release, Dhan identity verification and portfolio reads used direct HTTP calls. Orders and reconciliation were Upstox-specific. The shared market-data worker and instrument master were also designed for Upstox; they cannot safely be relabelled as personal Dhan feeds.

The new Dhan path is: authenticated owner → DhanClient → official SDK business method → guarded SDK HTTP transport → normalized financial fields → existing portfolio snapshots or owner-scoped research cache → existing GnKAlgo UI. The portfolio worker retains the first-snapshot autoflush correction and failure backoff from commit 6035cce.

Affected files are concentrated in `backend/app/brokers/dhan`, the existing Dhan verifier and portfolio adapter, portfolio field mappings, dashboard summary, the new frontend DhanWorkspace, navigation, requirements, tests and deployment documentation. Existing paper routes and Upstox execution orchestration are preserved.

## SDK compatibility and attribution

- Dependency: **dhanhq==2.3.0**, the official package. No SDK repository is vendored.
- Production Docker uses Python 3.12. The package declares Python >=3.10; local automated compatibility tests used Python 3.14. A real Docker/ARM build is still required on the VM.
- Official DhanContext/dhanhq methods are used for holdings, positions, funds, order/trade books, quotes, expiries, option chain, history and past trades.
- A DhanHTTP subclass guards transport behavior: fixed hosts/paths, TLS verification, no redirects, bounded response size, finite timeouts, shared per-client rate limits and no automatic request retries. This also avoids the SDK default exception logging of raw provider details. The profile/renewal endpoint calls use this same SDK HTTP boundary; the SDK's browser-opening DhanLogin helper is not run on the server.
- The SDK's daily trade-book trailing slash is canonicalized to the documented /trades endpoint. Quote segment-map payloads do not receive an extra dhanClientId segment; owner identity remains in headers.
- Dependencies resolved successfully and `pip check` passed locally. MIT attribution is recorded in THIRD_PARTY_NOTICES.md and remains in the installed package.

Official references: [SDK repository](https://github.com/dhan-oss/DhanHQ-py), [SDK package](https://pypi.org/project/dhanhq/2.3.0/), [Dhan documentation](https://docs.dhanhq.co/), [portfolio](https://dhanhq.co/docs/v2/portfolio/), [historical candles](https://dhanhq.co/docs/v2/historical-data/), [statements](https://dhanhq.co/docs/v2/statements/). Reviewed 4 November 2026.

## Implemented and tested

1. **SDK foundation:** pinned dependency, owner-bound SDK service, guarded transport, normalized errors and attribution.
2. **Token-based authentication:** existing client-ID/access-token connector now verifies Dhan through the SDK HTTP boundary. Expiry validation and encrypted storage are reused. Explicit session renewal verifies the new token's identity/expiry before sealing it; tokens are never returned. Existing connection management handles local disconnect. Application login/MFA remains separate.
3. **Account and portfolio:** existing holdings/positions/funds/order/trade snapshots now call SDK business methods. Additional buy/sell averages, order type/trigger price, actual Dhan executed trade fields and withdrawable funds are mapped when present. The dashboard holdings-value card reads owned snapshots instead of a fixed unavailable placeholder. It does not sum holdings, margins and positions into synthetic net worth.
4. **Personal market snapshots:** LTP/OHLC/full-quote requests for explicitly chosen Dhan security IDs and segments. These are owner-account REST snapshots with timestamps, not a streaming feed or cross-user distribution service.
5. **Option-chain research:** expiry loading, strike-wise CE/PE LTP, OI, IV, Greeks and reported bid/ask fields; underlying price and complete-data PCR. Missing values remain unknown.
6. **Historical research:** native 1/5/15/25/60-minute and daily candles; requested 2/3-minute bars derived from 1-minute bars, and 30-minute bars from 15-minute bars. Derived NSE/BSE sessions anchor at 09:15 IST and partial/gapped buckets are marked incomplete. Incomplete buckets are excluded from indicator calculations. API ranges are bounded to 90 days and 10,000 returned candles; larger research datasets need windowing/persistence work.
7. **Technical indicators:** EMA 9/20/60, Wilder RSI/ATR, MACD/signal, same-day VWAP, recent support/resistance, EMA-direction label and volume-breakout calculation. These are deterministic research values. Warmup gaps remain null; there is no fabricated ML confidence or model-backed recommendation.
8. **Broker trade history:** paged historical trades with date, symbol and side filters, real execution IDs/prices/quantities, and current-page CSV download. Cost-basis-dependent trade P&L and charges are not invented.
9. **Frontend:** `/user/dhan` reuses the existing navigation/theme/authentication. Account, Market watch, Option chain, Historical research and Trade history tabs include request errors, masked client identity, snapshot timestamps, manual refresh, token-renew confirmation, a candlestick chart and responsive tables. Unified `/user/portfolio` remains the place for cross-broker balances and positions.

Dhan holdings do not necessarily include an LTP. A successful holdings sync can therefore show quantity and investment cost while current value/P&L remain unavailable. An ambiguous `ALL` exchange/security ID is never priced by guessing a different exchange's instrument.

## Remaining master-plan phases — not implemented or activated

- Registered Dhan OAuth and PIN/TOTP token generation. These need a reviewed web callback/state flow and actual application configuration; no PIN/TOTP secrets are collected by this release.
- Dhan order placement/modify/cancel/exit, MARKET/SL/SL-M support, all exchange/product combinations, durable Dhan intents, order-update reconciliation and advanced risk orchestration. The current execution ledger is Upstox-specific. Direct SDK write methods are intentionally rejected by the account/research transport. Dhan execution needs its own tested integration with idempotency, instrument mapping, broker approvals and reconciliation before it can be marked ready.
- Dhan MarketFeed/OrderUpdate WebSockets, per-account centralized subscription/lease management, index watchlists and market-status/trend streaming. Existing Upstox market services are unchanged. The frontend labels this release's prices as snapshots.
- Expired-option APIs, deeper market depth, Greeks/IV models beyond reported fields, long-term candle storage, full backtesting and corporate-action/cost-ledger reconstruction.
- Trained ML model inference, confidence, CE/PE recommendation aggregation, risk-sized automatic signals and live strategy dispatch. No trained model or validated training artifacts were supplied; the API explicitly reports NOT_CONFIGURED.
- STOP ALL ALGOS with tracked broker cancellation and optional square-off; maximum-profit and capital-allocation extensions; Super/Forever/Conditional/P&L-exit/multi-leg/static-IP configuration. Existing kill switches keep their existing scope and are not relabelled as liquidation controls.

These items require separate implementation/testing; available SDK methods alone are not completion evidence.

## API contracts and security

New owner-authenticated endpoints:

- GET `/api/v1/dhan/status`: masked owned accounts, SDK version and truthful capability flags.
- GET `/api/v1/dhan/profile?account_id=...`: safe profile fields.
- POST `/api/v1/dhan/accounts/{id}/renew`: explicit verified renewal; no token in response.
- POST `/api/v1/dhan/quotes`: account_id, segment, up to 50 distinct positive security_ids and mode ltp/ohlc/full.
- GET `/api/v1/dhan/expiries`: account_id, underlying security_id and segment.
- GET `/api/v1/dhan/option-chain`: account_id, underlying security_id, segment and expiry.
- GET `/api/v1/dhan/history`: account_id, security_id, segment, instrument, from_date, to_date and interval.
- GET `/api/v1/dhan/trade-history`: account_id, from_date, to_date, broker page, optional symbol and side.

POSTs use existing session CSRF protection. Owned-account checks precede broker calls; active credentials and expiry are checked even before returning cached data. Caches include owner/account and credential-version fingerprints. Fixed numeric/nested-field projections suppress unknown response properties. Credential ciphertext, access tokens and raw broker errors are never returned. CSV cells beginning with spreadsheet formula prefixes are escaped. Broker books stay separate from GNK's recorded execution history.

No new database schema/migration is needed beyond existing migration 0009. No new environment values or changes to live-trading flags are needed for this release. Dhan data subscriptions/permissions must authorize the requested endpoints; an authentication success does not prove data access.

## Deployment

Source publication is separate from VM deployment. SSH with the currently available key was rejected; no Oracle VM change was performed from this development session.

After this commit is available, use your existing VM shell:

```bash
cd /opt/gnk
git pull --ff-only
# Set the existing backup public-key fingerprint in this shell if it is not exported.
# export GNK_BACKUP_RECIPIENT="your existing full fingerprint"
GNK_ENV=production ./deploy/redeploy_dhan.sh
```

The script checks secret permissions, starts dependencies, builds all matching Python/frontend service images, creates an encrypted backup, provisions existing grants, runs the existing migration verification, recreates services and Nginx, checks environment/schema/Redis/HTTP health, and verifies the installed SDK version. It does not edit .env, regenerate credentials or modify Nginx configuration. Recreating Nginx refreshes upstream container addresses.

After deployment, sign in to `/user/portfolio` and `/user/dhan`. Verify your own Dhan holdings/funds, profile and permitted data reads. Do not place orders to validate this release. If a step fails, stop and inspect that step; do not delete volumes or bypass schema readiness.

For rollback, preserve the encrypted backup and current database. Previous image tags can be restored with an explicit image-version deployment plan; no schema downgrade is required by this SDK-only release. Do not blindly restore an old database on a running trading system, since newer order/account records could be lost.

## Verification results

- Full backend suite: **186 passed, 15 skipped** (Linux/PostgreSQL-dependent checks need their CI environments).
- Focused SDK/portfolio/verifier suite after final response refinements: **60 passed**.
- Production TypeScript/Vite build passed; `pip check` reported no broken dependencies.
- Headless Chromium with the real local API and SDK business methods over mock broker transport passed profile masking, quotes, expiry/option-chain loading, candle chart/indicators, trade-history/CSV download and all five tabs at 1440/768/390 widths. No page exceptions, page overflow or order mutations occurred.
- Broker credentials and responses in these tests were offline fixtures. Production Dhan permissions, token renewal, data access and Docker/ARM compatibility have not been verified on the VM.
- Local Git Bash syntax execution was blocked by the Windows MSYS runtime; the repository's Linux service-controls CI performs `bash -n` on deploy scripts.
