"""Evaluate a locked paper-ledger snapshot without sharing a database session."""
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, TypeVar


@dataclass(frozen=True, slots=True)
class PositionExposure:
    symbol: str
    quantity: int
    average_price: Decimal


@dataclass(frozen=True, slots=True)
class OrderExposure:
    symbol: str
    side: Literal['BUY', 'SELL']
    quantity: int
    price: Decimal


@dataclass(frozen=True, slots=True)
class RiskSnapshot:
    order: OrderExposure
    positions: tuple[PositionExposure, ...]
    pending: tuple[OrderExposure, ...]
    daily_order_count: int | None
    daily_loss: Decimal | None
    max_quantity: int
    max_order_value: Decimal
    max_daily_orders: int
    max_daily_loss: Decimal
    max_positions: int
    paper_collateral: Decimal


_workers = ThreadPoolExecutor(max_workers=3, thread_name_prefix='gnk-risk')


def order_limits(snapshot: RiskSnapshot) -> str | None:
    order = snapshot.order
    if order.quantity > snapshot.max_quantity or order.quantity * order.price > snapshot.max_order_value:
        return 'Order exceeds personal risk limits'
    if snapshot.daily_order_count is not None and snapshot.daily_order_count >= snapshot.max_daily_orders:
        return 'Daily order limit reached'
    if snapshot.daily_loss is not None and snapshot.daily_loss >= snapshot.max_daily_loss:
        return 'Realized loss limit reached'
    return None


def position_limits(snapshot: RiskSnapshot) -> str | None:
    order = snapshot.order
    if order.side == 'SELL':
        held = sum(p.quantity for p in snapshot.positions if p.symbol == order.symbol)
        reserved = sum(o.quantity for o in snapshot.pending if o.side == 'SELL' and o.symbol == order.symbol)
        if held - reserved < order.quantity:
            return 'Insufficient unreserved position quantity'
    else:
        symbols = {p.symbol for p in snapshot.positions if p.quantity}
        symbols.update(o.symbol for o in snapshot.pending if o.side == 'BUY')
        if len(symbols | {order.symbol}) > snapshot.max_positions:
            return 'Position limit reached'
    return None


def collateral_limits(snapshot: RiskSnapshot) -> str | None:
    order = snapshot.order
    if order.side == 'BUY':
        used = sum((p.average_price * p.quantity for p in snapshot.positions), Decimal(0))
        reserved = sum((o.price * o.quantity for o in snapshot.pending if o.side == 'BUY'), Decimal(0))
        if used + reserved + order.price * order.quantity > snapshot.paper_collateral:
            return 'Insufficient paper collateral'
    return None


def rejection_reason(snapshot: RiskSnapshot) -> str | None:
    return first_rejection(snapshot, order_limits, position_limits, collateral_limits)


Snapshot = TypeVar('Snapshot')


def first_rejection(snapshot: Snapshot, *checks: Callable[[Snapshot], str | None]) -> str | None:
    futures = [_workers.submit(check, snapshot) for check in checks]
    # Read results in policy order so the first rejection is deterministic.
    results = [future.result() for future in futures]
    return next((result for result in results if result is not None), None)
