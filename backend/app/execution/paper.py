from datetime import timezone
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.compliance.service import require_disclosure
from app.core.config import digest, ident, now, settings
from app.database.session import db
from app.execution.routes import risk_for
from app.models.trading import Order, PaperMark, PlatformControl, Position, Strategy
from app.security.authentication import auth
from app.security.ownership import owned
from app.services.accounts import audit

router = APIRouter(prefix='/api/v1/gnk/paper', tags=['GNK paper trading'])

Price = Annotated[Decimal, Field(gt=0, le=10000000, max_digits=20, decimal_places=4)]
Quantity = Annotated[int, Field(ge=1, le=100000)]
Symbol = Annotated[str, Field(pattern=r'^[A-Z0-9_.-]{1,40}$')]
Product = Literal['DELIVERY', 'INTRADAY']
ZERO = Decimal('0')
MARKET_TZ = ZoneInfo('Asia/Kolkata')


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class LimitOrder(Input):
    strategy_id: str
    symbol: Symbol
    side: Literal['BUY', 'SELL']
    quantity: Quantity
    price: Price
    idempotency_key: str = Field(min_length=8, max_length=80)


class AmendOrder(Input):
    quantity: Quantity
    price: Price
    version: int = Field(ge=1)


class ReplayPrice(Input):
    symbol: Symbol
    price: Price
    sequence: int = Field(ge=1, le=2147483647)


class ProtectPosition(Input):
    stop_loss: Price | None = None
    target: Price | None = None


class ConvertPosition(Input):
    product: Product


class Collateral(Input):
    amount: Annotated[Decimal, Field(gt=0, le=1000000000, decimal_places=4)]


def paper_order_public(order):
    return {
        'id': order.id, 'strategy_id': order.strategy_id, 'symbol': order.symbol,
        'side': order.side, 'quantity': order.quantity, 'price': str(order.price),
        'mode': 'paper', 'status': order.status, 'version': order.version,
        'created_at': order.created_at,
        'executed_at': (order.executed_at or order.created_at) if order.status == 'filled' else None,
        'execution_price': str(order.execution_price or order.price) if order.status == 'filled' else None,
        'execution_reason': order.execution_reason,
        'realized_pnl': str(order.realized_pnl),
    }


def paper_orders(uid):
    return select(Order).where(Order.user_id == uid, Order.mode == 'paper')


def pending_orders(s, uid, exclude=None):
    query = paper_orders(uid).where(Order.status == 'open')
    if exclude:
        query = query.where(Order.id != exclude)
    return list(s.scalars(query.order_by(Order.created_at, Order.id)))


def account_positions(s, uid):
    return {p.symbol: p for p in s.scalars(select(Position).where(Position.user_id == uid))}


def margin(positions, pending):
    used = sum((p.average_price * p.quantity for p in positions.values()), ZERO)
    reserved = sum((o.price * o.quantity for o in pending if o.side == 'BUY'), ZERO)
    return used, reserved


def stopped(s, risk):
    platform = s.get(PlatformControl, 'global')
    return risk.kill_switch or bool(platform and platform.kill_switch)


def trading_day_start():
    return now().astimezone(MARKET_TZ).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def daily_loss(s, uid):
    return -s.scalar(select(func.coalesce(func.sum(Order.realized_pnl), 0)).where(
        Order.user_id == uid, Order.mode == 'paper', Order.status == 'filled',
        func.coalesce(Order.executed_at, Order.created_at) >= trading_day_start(),
    ))


def validate_order(s, uid, risk, order, *, new=False, exclude=None):
    if stopped(s, risk):
        raise HTTPException(409, 'Emergency stop active')
    if order.quantity > risk.max_quantity or order.quantity * order.price > risk.max_order_value:
        raise HTTPException(422, 'Order exceeds personal risk limits')
    if new:
        count = s.scalar(select(func.count()).select_from(
            paper_orders(uid).where(Order.created_at >= trading_day_start()).subquery()
        ))
        if count >= risk.max_daily_orders:
            raise HTTPException(422, 'Daily order limit reached')

    positions = account_positions(s, uid)
    pending = pending_orders(s, uid, exclude)
    position = positions.get(order.symbol)
    if order.side == 'SELL':
        reserved = sum(o.quantity for o in pending if o.side == 'SELL' and o.symbol == order.symbol)
        if not position or position.quantity - reserved < order.quantity:
            raise HTTPException(422, 'Insufficient unreserved position quantity')
        return

    if daily_loss(s, uid) >= risk.max_daily_loss:
        raise HTTPException(422, 'Realized loss limit reached')
    symbols = {p.symbol for p in positions.values() if p.quantity}
    symbols.update(o.symbol for o in pending if o.side == 'BUY')
    if len(symbols | {order.symbol}) > risk.max_positions:
        raise HTTPException(422, 'Position limit reached')
    used, reserved = margin(positions, pending)
    if used + reserved + order.quantity * order.price > risk.paper_collateral:
        raise HTTPException(422, 'Insufficient paper collateral')


def apply_fill(s, order, price, reason):
    position = s.scalar(select(Position).where(
        Position.user_id == order.user_id, Position.symbol == order.symbol,
    ))
    if position is None:
        position = Position(user_id=order.user_id, symbol=order.symbol, quantity=0,
                            average_price=ZERO, realized_pnl=ZERO)
        s.add(position)
    order.realized_pnl = ZERO
    if order.side == 'BUY':
        cost = position.average_price * position.quantity + price * order.quantity
        if position.quantity == 0:
            position.product = 'DELIVERY'
        position.quantity += order.quantity
        position.average_price = (cost / position.quantity).quantize(Decimal('0.0001'))
    else:
        if position.quantity < order.quantity:
            raise HTTPException(409, 'Insufficient position quantity')
        order.realized_pnl = (price - position.average_price) * order.quantity
        position.realized_pnl += order.realized_pnl
        position.quantity -= order.quantity
        if position.quantity == 0:
            position.average_price = ZERO
            position.stop_loss = None
            position.target = None
    order.status = 'filled'
    order.version += 1
    order.executed_at = now()
    order.execution_price = price
    order.execution_reason = reason
    audit(s, order.user_id, 'gnk_paper_filled:' + order.id)
    s.flush()


def cancel(s, order):
    order.status = 'cancelled'
    order.version += 1
    audit(s, order.user_id, 'gnk_paper_cancelled:' + order.id)


def close_position(s, position, price, reason):
    last_order = s.scalar(paper_orders(position.user_id).where(
        Order.symbol == position.symbol, Order.status == 'filled',
    ).order_by(func.coalesce(Order.executed_at, Order.created_at).desc(), Order.id).limit(1))
    if last_order is None:
        raise HTTPException(409, 'Position execution history unavailable')
    key = ident()
    order = Order(id=key, user_id=position.user_id, strategy_id=last_order.strategy_id,
                  symbol=position.symbol, side='SELL', quantity=position.quantity,
                  price=price, idempotency_key='exit:' + key, request_hash=digest(key),
                  mode='paper', status='open', version=0)
    s.add(order)
    apply_fill(s, order, price, reason)
    return order


def start_write(s, uid):
    if not settings.paper_trading_enabled:
        raise HTTPException(409, 'Paper trading disabled')
    return risk_for(s, uid)


class PaperStrategy(Input):
    name: str = Field(min_length=2, max_length=100, pattern=r'^.*\S.*$')


@router.get('/strategies')
def strategies(u=Depends(auth), s: Session = Depends(db)):
    query = select(Strategy).where(Strategy.user_id == u.id).order_by(Strategy.name, Strategy.id)
    return [{'id': item.id, 'name': item.name} for item in s.scalars(query)]


@router.post('/strategies', status_code=201)
def create_strategy(data: PaperStrategy, u=Depends(require_disclosure), s: Session = Depends(db)):
    start_write(s, u.id)
    strategy = Strategy(user_id=u.id, name=data.name.strip())
    s.add(strategy)
    audit(s, u.id, 'gnk_paper_strategy_created')
    s.commit()
    return {'id': strategy.id, 'name': strategy.name}


@router.post('/orders', status_code=201)
def place(data: LimitOrder, u=Depends(require_disclosure), s: Session = Depends(db)):
    risk = start_write(s, u.id)
    request_hash = digest('gnk-limit:' + json.dumps(data.model_dump(mode='json'), sort_keys=True))
    previous = s.scalar(paper_orders(u.id).where(Order.idempotency_key == data.idempotency_key))
    if previous:
        if previous.request_hash != request_hash:
            raise HTTPException(409, 'Idempotency key reused with different request')
        return paper_order_public(previous)
    if data.idempotency_key.startswith('exit:'):
        raise HTTPException(422, 'Reserved idempotency key prefix')
    owned(s, Strategy, data.strategy_id, u.id)
    validate_order(s, u.id, risk, data, new=True)
    order = Order(id=ident(), user_id=u.id, **data.model_dump(), request_hash=request_hash,
                  mode='paper', status='open')
    s.add(order)
    audit(s, u.id, 'gnk_paper_placed:' + order.id)
    s.commit()
    return paper_order_public(order)


@router.get('/orders')
def book(status: Literal['open', 'filled', 'cancelled'] | None = None,
         offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
         u=Depends(auth), s: Session = Depends(db)):
    query = paper_orders(u.id)
    if status:
        query = query.where(Order.status == status)
    return [paper_order_public(o) for o in s.scalars(
        query.order_by(Order.created_at.desc(), Order.id).offset(offset).limit(limit)
    )]


@router.get('/executions')
def executions(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
               u=Depends(auth), s: Session = Depends(db)):
    query = paper_orders(u.id).where(Order.status == 'filled').order_by(
        func.coalesce(Order.executed_at, Order.created_at).desc(), Order.id
    )
    return [paper_order_public(o) for o in s.scalars(query.offset(offset).limit(limit))]


@router.get('/orders/{order_id}')
def status(order_id: str, u=Depends(auth), s: Session = Depends(db)):
    order = s.scalar(paper_orders(u.id).where(Order.id == order_id))
    if order is None:
        raise HTTPException(404, 'Order not found')
    return paper_order_public(order)


def open_order(s, uid, order_id, version):
    order = s.scalar(paper_orders(uid).where(Order.id == order_id))
    if order is None:
        raise HTTPException(404, 'Order not found')
    if order.status != 'open' or order.version != version:
        raise HTTPException(409, 'Order state or version changed')
    return order


@router.patch('/orders/{order_id}')
def modify(order_id: str, data: AmendOrder, u=Depends(require_disclosure), s: Session = Depends(db)):
    risk = start_write(s, u.id)
    order = open_order(s, u.id, order_id, data.version)
    with s.no_autoflush:
        order.quantity = data.quantity
        order.price = data.price
        validate_order(s, u.id, risk, order, exclude=order.id)
    order.version += 1
    audit(s, u.id, 'gnk_paper_modified:' + order.id)
    s.commit()
    return paper_order_public(order)


@router.delete('/orders/{order_id}')
def cancel_order(order_id: str, version: int = Query(ge=1), u=Depends(auth), s: Session = Depends(db)):
    risk_for(s, u.id)
    order = open_order(s, u.id, order_id, version)
    cancel(s, order)
    s.commit()
    return paper_order_public(order)


def position_rows(s, uid, positions, state='all'):
    marks = {m.symbol: m.price for m in s.scalars(select(PaperMark).where(PaperMark.user_id == uid))}
    result = []
    for p in sorted(positions.values(), key=lambda p: p.symbol):
        current_state = 'open' if p.quantity else 'closed'
        if state not in ('all', current_state):
            continue
        mark = marks.get(p.symbol)
        unrealized = ZERO if not p.quantity else None
        if p.quantity and mark is not None:
            unrealized = (mark - p.average_price) * p.quantity
        result.append({
            'id': p.id, 'symbol': p.symbol, 'state': current_state, 'product': p.product,
            'quantity': p.quantity, 'average_price': str(p.average_price),
            'realized_pnl': str(p.realized_pnl),
            'unrealized_pnl': str(unrealized) if unrealized is not None else None,
            'mark': str(mark) if mark is not None else None,
            'stop_loss': str(p.stop_loss) if p.stop_loss is not None else None,
            'target': str(p.target) if p.target is not None else None,
        })
    return result



@router.get('/positions')
def positions(state: Literal['open', 'closed', 'all'] = 'all', u=Depends(auth), s: Session = Depends(db)):
    return position_rows(s, u.id, account_positions(s, u.id), state)


@router.get('/portfolio')
def portfolio(u=Depends(auth), s: Session = Depends(db)):
    # Use the paper ledger's user lock to keep positions, reservations, and fills consistent.
    risk = risk_for(s, u.id)
    balances = account_positions(s, u.id)
    rows = position_rows(s, u.id, balances)
    holdings = [row for row in rows if row['state'] == 'open']
    used, reserved = margin(balances, pending_orders(s, u.id))
    realized = sum((p.realized_pnl for p in balances.values()), ZERO)
    marked = [row for row in holdings if row['mark'] is not None]
    unrealized = sum((Decimal(row['unrealized_pnl']) for row in marked), ZERO)
    unpriced = len(holdings) - len(marked)
    marked_value = sum((Decimal(row['mark']) * row['quantity'] for row in marked), ZERO)
    recent = list(s.scalars(paper_orders(u.id).order_by(Order.created_at.desc(), Order.id).limit(25)))
    result = {
        'mode': 'PAPER',
        'as_of': now(),
        'holdings': holdings,
        'orders': [paper_order_public(order) for order in recent],
        'funds': {
            'collateral': str(risk.paper_collateral), 'used': str(used), 'reserved': str(reserved),
            'available': str(risk.paper_collateral - used - reserved),
        },
        'pnl': {
            'realized': str(realized),
            'unrealized': str(unrealized) if not unpriced else None,
            'total': str(realized + unrealized) if not unpriced else None,
            'marked_value': str(marked_value) if not unpriced else None,
            'unpriced_holdings': unpriced,
            'by_symbol': rows,
        },
    }
    s.commit()
    return result


def active_position(s, uid, position_id):
    position = owned(s, Position, position_id, uid)
    if not position.quantity:
        raise HTTPException(409, 'Position is closed')
    return position


@router.put('/positions/{position_id}/product')
def convert(position_id: str, data: ConvertPosition, u=Depends(require_disclosure), s: Session = Depends(db)):
    risk = start_write(s, u.id)
    position = active_position(s, u.id, position_id)
    if stopped(s, risk):
        raise HTTPException(409, 'Emergency stop active')
    if any(o.symbol == position.symbol for o in pending_orders(s, u.id)):
        raise HTTPException(409, 'Cancel working orders before conversion')
    position.product = data.product
    audit(s, u.id, 'gnk_paper_converted:' + position.id)
    s.commit()
    return {'id': position.id, 'product': position.product}


@router.put('/positions/{position_id}/protection')
def protect(position_id: str, data: ProtectPosition, u=Depends(require_disclosure), s: Session = Depends(db)):
    start_write(s, u.id)
    position = active_position(s, u.id, position_id)
    mark = s.get(PaperMark, (u.id, position.symbol))
    reference = mark.price if mark else position.average_price
    if data.stop_loss is not None and data.stop_loss >= reference:
        raise HTTPException(422, 'Stop-loss must be below the reference price')
    if data.target is not None and data.target <= reference:
        raise HTTPException(422, 'Target must be above the reference price')
    position.stop_loss = data.stop_loss
    position.target = data.target
    audit(s, u.id, 'gnk_paper_protection:' + position.id)
    s.commit()
    return {'id': position.id, **data.model_dump(mode='json')}


@router.post('/positions/{position_id}/square-off')
def square_off(position_id: str, u=Depends(auth), s: Session = Depends(db)):
    start_write(s, u.id)
    position = active_position(s, u.id, position_id)
    mark = s.get(PaperMark, (u.id, position.symbol))
    if mark is None:
        raise HTTPException(409, 'Replay a price before squaring off')
    for order in pending_orders(s, u.id):
        if order.symbol == position.symbol:
            cancel(s, order)
    order = close_position(s, position, mark.price, 'SQUARE_OFF')
    s.commit()
    return paper_order_public(order)


@router.get('/risk/margin')
def margin_status(u=Depends(auth), s: Session = Depends(db)):
    risk = risk_for(s, u.id)
    used, reserved = margin(account_positions(s, u.id), pending_orders(s, u.id))
    result = {'collateral': str(risk.paper_collateral), 'used': str(used),
              'reserved': str(reserved), 'available': str(risk.paper_collateral - used - reserved),
              'stopped': stopped(s, risk), 'daily_realized_loss': str(max(ZERO, daily_loss(s, u.id)))}
    s.commit()
    return result


@router.put('/risk/margin')
def set_margin(data: Collateral, u=Depends(require_disclosure), s: Session = Depends(db)):
    risk = start_write(s, u.id)
    used, reserved = margin(account_positions(s, u.id), pending_orders(s, u.id))
    if data.amount < used + reserved:
        raise HTTPException(422, 'Collateral cannot be below committed exposure')
    risk.paper_collateral = data.amount
    audit(s, u.id, 'gnk_paper_collateral')
    s.commit()
    return {'collateral': str(risk.paper_collateral)}


@router.post('/risk/emergency-exit')
def emergency_exit(u=Depends(auth), s: Session = Depends(db)):
    risk = start_write(s, u.id)
    risk.kill_switch = True
    for order in pending_orders(s, u.id):
        cancel(s, order)
    executions = []
    unpriced = []
    for position in account_positions(s, u.id).values():
        if not position.quantity:
            continue
        mark = s.get(PaperMark, (u.id, position.symbol))
        if mark is None:
            unpriced.append(position.symbol)
            continue
        order = close_position(s, position, mark.price, 'EMERGENCY_EXIT')
        executions.append(paper_order_public(order))
    audit(s, u.id, 'gnk_paper_emergency_exit')
    s.commit()
    return {'stopped': True, 'executions': executions, 'unpriced_positions': sorted(unpriced)}


@router.post('/replay/price')
def replay(data: ReplayPrice, u=Depends(require_disclosure), s: Session = Depends(db)):
    risk = start_write(s, u.id)
    mark = s.get(PaperMark, (u.id, data.symbol))
    if mark is not None and data.sequence <= mark.sequence:
        if data.sequence == mark.sequence and data.price == mark.price:
            return {'duplicate': True, 'executions': []}
        raise HTTPException(409, 'Replay sequence must increase per symbol')
    if mark is None:
        mark = PaperMark(user_id=u.id, symbol=data.symbol)
        s.add(mark)
    mark.price = data.price
    mark.sequence = data.sequence
    orders = [o for o in pending_orders(s, u.id) if o.symbol == data.symbol]
    position = account_positions(s, u.id).get(data.symbol)
    filled = []
    if position and position.quantity:
        reason = None
        if position.stop_loss is not None and data.price <= position.stop_loss:
            reason = 'STOP_LOSS'
        elif position.target is not None and data.price >= position.target:
            reason = 'TARGET'
        if reason:
            for order in orders:
                cancel(s, order)
            filled.append(close_position(s, position, data.price, reason))
            orders = []
    if not stopped(s, risk):
        for order in orders:
            crosses = data.price <= order.price if order.side == 'BUY' else data.price >= order.price
            if not crosses:
                continue
            try:
                validate_order(s, u.id, risk, order, exclude=order.id)
            except HTTPException as error:
                if error.status_code not in (409, 422):
                    raise
                continue
            apply_fill(s, order, data.price, 'LIMIT')
            filled.append(order)
    s.commit()
    return {'duplicate': False, 'executions': [paper_order_public(o) for o in filled]}
