# GNK paper trading

GNK runs an authenticated, broker-independent trading simulator under
`/api/v1/gnk/paper`. It uses manually supplied prices and virtual collateral.
All fills are simulated long-only trades. There are no fees, liquidity limits,
partial fills, funding changes from P&L, or expiry rules.

## Run locally

1. From the GNK repository, configure the normal GNK development environment.
2. Run `python -m alembic -c backend/alembic.ini upgrade head` with
   `PYTHONPATH=backend` and the application's database configuration.
3. Run the backend using GNK's normal startup process. Use the API schema at
   `/docs` where enabled. Sign in and acknowledge the current disclosure.
   Send the session cookie and `X-CSRF-Token` on authenticated writes.
4. Create a strategy, submit a limit order, then replay prices for its symbol.
   Each new replay uses an increasing integer sequence for that user and
   symbol. Matching orders fill in creation order at the replay price.
   A replay repeated with the same sequence and price has no additional effect.

## OMS

- `GET /strategies` and `POST /strategies` list and create owner-scoped strategies.
- `POST /orders` accepts strategy ID, symbol, side, quantity, limit price, and
  an idempotency key. It creates an open order.
- `GET /orders` shows the order book and supports status filtering and pagination.
  `GET /orders/{id}` shows the current state and version.
- `PATCH /orders/{id}` changes price and quantity. `DELETE /orders/{id}?version=1`
  cancels an open order. Both require the current version.
- `GET /executions` lists fills with execution price, timestamp, reason, and
  realized P&L. Historical filled paper orders use their original price and
  creation time when execution fields are absent.

## PMS

- `GET /positions?state=all` returns open and closed symbol balances, weighted
  average entry price, cumulative realized P&L, and unrealized P&L at the latest
  replayed price. Open positions without a mark return null unrealized P&L.
  The execution history retains previous closes when a symbol is reopened.
- `PUT /positions/{id}/product` changes a position between simulated delivery
  and intraday classification. Both classifications use the same collateral
  rules. There is no automatic end-of-day liquidation.
- `POST /positions/{id}/square-off` cancels working orders for that symbol and
  closes the position at its latest replayed price. It requires a saved price.

## RMS

- `GET /risk/margin` reports virtual collateral, used collateral, buy order
  reservations, and available collateral. `PUT /risk/margin` changes the
  virtual collateral cap. Open sell orders reserve shares.
- Native orders use GNK's existing account-level order size, notional,
  order-count, position-count, daily realized loss, and emergency-stop settings.
  The trading day is measured in Asia/Kolkata.
- `PUT /positions/{id}/protection` replaces the stop-loss and target. A replay
  that crosses a threshold closes the position at the replay price and
  cancels the symbol's working orders before they can re-enter.
- `POST /risk/emergency-exit` activates the user's GNK kill switch, cancels
  working paper orders, and closes priced paper positions. Symbols without a
  saved price are reported as unpriced. Replay a price and retry to close those
  symbols. The existing GNK risk emergency-stop route can clear the user switch.

Run the integration tests from the repository root with `PYTHONPATH=backend`
and `python -m pytest -q tests/integration/test_gnk_paper.py`.
