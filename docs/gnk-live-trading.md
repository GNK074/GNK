# GNK trading workspace

The signed-in **Trading** dashboard at `/user/trading` operates GNK's native
paper OMS, PMS, and RMS. Run the application and database migration as
described in [GNK paper trading](gnk-paper-trading.md).

Use the dashboard to create a strategy, place a paper limit order, and replay
a price for its symbol. The order book shows the status and fill price.
Positions expose P&L, conversion, square-off, stop-loss, and target controls.
Risk controls display paper collateral and offer an emergency exit.

## Live API

The authenticated `GET /api/v1/gnk/live/status` reports live availability.
`POST /api/v1/gnk/live/orders` validates a GNK instrument ID, client order ID,
side, quantity, limit price, and explicit real-money confirmation. Until an
execution connection exists, valid submissions return HTTP 503. The API
records no live orders or synthetic fills on this path.

## Execution connection boundary

`backend/app/execution/connection.py` defines an independent connection
contract. It takes a venue-neutral GNK order intent and exposes placement,
amendment, and cancellation operations. GNK core contains no implementation
or setup for that connection. Any future adapter will need to map GNK
instruments, handle external order identity, reconcile fills, and expose
venue-specific margin and position capabilities before real-money routing
can be enabled.
