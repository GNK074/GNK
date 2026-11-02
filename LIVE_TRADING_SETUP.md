# Live trading status: BLOCKED

This release has no live execution or reconciliation adapter. LIVE_TRADING_ENABLED=true is rejected at startup. POST /api/v1/live/orders checks authenticated strategy and broker-account ownership and returns a blocked readiness result. It never calls a broker order API. An environment flag, admin click or complete evidence count cannot override the unavailable runtime.

Production approval independently rechecks 18 current requirement records. The API also reports the hard runtime blocker even when all reviewer evidence is current. No customer account has a path to live_authorized=true in this release. Authentication availability does not imply broker approval, trading permission, market-data licensing, static IP eligibility or margin validation.

Paper simulation is implemented separately: manually entered prices, immediate long-only fills, no exchange connectivity, no slippage/fees/margin model. User-specific quantity, order-value, order-count, position-count and realized daily-loss limits apply. Per-user parent-row locking serializes paper actions in PostgreSQL. Idempotency keys replay the same order or reject changed payloads. This is not a realistic broker sandbox or a trading recommendation.

User, broker-account and platform stops are persisted. User/platform stops prevent new paper fills; account stops revoke the account's local live authorization. There are no pending real broker orders to cancel. Real cancellation/reconciliation is still required before the stop controls can be claimed as a live emergency system. No liquidation is performed.
