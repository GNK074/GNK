"""Venue-neutral, fail-closed validation for live GNK order intents."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import now, settings
from app.execution.connection import LiveOrderIntent
from app.execution.paper_risk import OrderExposure, PositionExposure, first_rejection
from app.execution.routes import risk_for
from app.models.trading import PlatformControl

MAX_SNAPSHOT_AGE = timedelta(seconds=15)


@dataclass(frozen=True, slots=True)
class LiveAccountRisk:
    user_id: str
    as_of: datetime
    instrument_id: str
    instrument_active: bool
    available_cash: Decimal  # Net of pending reservations and other holds.
    daily_loss: Decimal
    daily_order_count: int
    positions: tuple[PositionExposure, ...]
    pending: tuple[OrderExposure, ...]


class LiveRiskSource(Protocol):
    def snapshot(self, user_id: str, instrument_id: str) -> LiveAccountRisk: ...


@dataclass(frozen=True, slots=True)
class LiveValidation:
    order: LiveOrderIntent
    account: LiveAccountRisk
    max_quantity: int
    max_order_value: Decimal
    max_daily_orders: int
    max_daily_loss: Decimal
    max_positions: int


def order_limits(data: LiveValidation) -> str | None:
    order = data.order
    account = data.account
    if order.quantity > data.max_quantity or order.limit_price * order.quantity > data.max_order_value:
        return 'Order exceeds live quantity or notional limits'
    if account.daily_order_count >= data.max_daily_orders:
        return 'Daily live order limit reached'
    if order.side == 'BUY' and account.daily_loss >= data.max_daily_loss:
        return 'Daily live loss limit reached'
    return None


def exposure_limits(data: LiveValidation) -> str | None:
    order, account = data.order, data.account
    held = sum(row.quantity for row in account.positions if row.symbol == order.instrument_id)
    reserved = sum(row.quantity for row in account.pending
                   if row.symbol == order.instrument_id and row.side == order.side)
    if order.side == 'SELL':
        if held - reserved < order.quantity:
            return 'Insufficient unreserved live position quantity'
    else:
        projected = held + reserved + order.quantity
        if projected > data.max_quantity or projected * order.limit_price > data.max_order_value:
            return 'Projected live instrument exposure exceeds risk limits'
        instruments = {row.symbol for row in account.positions if row.quantity}
        instruments.update(row.symbol for row in account.pending if row.side == 'BUY')
        if len(instruments | {order.instrument_id}) > data.max_positions:
            return 'Live position limit reached'
    return None


def funds_limits(data: LiveValidation) -> str | None:
    if data.order.side == 'BUY' and data.order.limit_price * data.order.quantity > data.account.available_cash:
        return 'Insufficient available live cash'
    return None


def validate_live_order(s: Session, user_id: str, intent: LiveOrderIntent, source: LiveRiskSource):
    if not settings.trading_enabled or not settings.live_trading_enabled:
        raise HTTPException(409, 'Live trading is disabled')
    risk = risk_for(s, user_id)
    platform = s.get(PlatformControl, 'global')
    if risk.kill_switch or not platform or platform.kill_switch:
        raise HTTPException(409, 'Emergency stop active')

    account = source.snapshot(user_id, intent.instrument_id)
    clock = now()
    if (account.user_id != user_id or account.instrument_id != intent.instrument_id
            or account.as_of.utcoffset() is None or not timedelta(0) <= clock - account.as_of <= MAX_SNAPSHOT_AGE
            or not account.available_cash.is_finite() or not account.daily_loss.is_finite()
            or account.daily_order_count < 0
            or any(row.quantity < 0 for row in account.positions)
            or any(row.quantity <= 0 for row in account.pending)):
        raise HTTPException(503, 'A fresh, valid live risk snapshot is required')
    if not account.instrument_active:
        raise HTTPException(422, 'Instrument is unavailable for live trading')

    validation = LiveValidation(
        order=intent, account=account, max_quantity=risk.max_quantity,
        max_order_value=risk.max_order_value, max_daily_orders=risk.max_daily_orders,
        max_daily_loss=risk.max_daily_loss, max_positions=risk.max_positions,
    )
    rejection = first_rejection(validation, order_limits, exposure_limits, funds_limits)
    if rejection:
        raise HTTPException(422, rejection)
