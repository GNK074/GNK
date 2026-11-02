import json
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.config import settings, digest, now
from app.database.session import db
from app.models.identity import User
from app.models.trading import Strategy, RiskConfiguration, Order, Position, PlatformControl, BrokerAccount, BrokerCredential
from app.schemas.trading import StrategyInput, RiskInput, PaperOrderInput, LiveOrderInput, SwitchInput
from app.security.authentication import auth, admin
from app.security.ownership import owned
from app.services.accounts import audit
router = APIRouter(prefix='/api/v1')

def order_public(o):
    return dict(id=o.id, strategy_id=o.strategy_id, symbol=o.symbol, side=o.side, quantity=o.quantity, price=str(o.price), mode=o.mode, status=o.status, created_at=o.created_at)

def risk_for(s, uid):
    s.scalar(select(User).where(User.id == uid).with_for_update())
    r = s.scalar(select(RiskConfiguration).where(RiskConfiguration.user_id == uid).with_for_update())
    if not r:
        r = RiskConfiguration(user_id=uid)
        s.add(r)
        s.flush()
    return r

@router.get('/strategies')
def strategies(u=Depends(auth), s: Session=Depends(db)):
    return [dict(id=x.id, name=x.name, approved=x.approved) for x in s.scalars(select(Strategy).where(Strategy.user_id == u.id))]

@router.post('/strategies', status_code=201)
def create_strategy(data: StrategyInput, u=Depends(auth), s: Session=Depends(db)):
    x = Strategy(user_id=u.id, name=data.name.strip())
    s.add(x)
    audit(s, u.id, 'strategy_created')
    s.commit()
    return dict(id=x.id, name=x.name, approved=x.approved)

@router.put('/strategies/{record_id}')
def update_strategy(record_id: str, data: StrategyInput, u=Depends(auth), s: Session=Depends(db)):
    x = owned(s, Strategy, record_id, u.id, lock=True)
    x.name = data.name.strip()
    s.commit()
    return dict(id=x.id, name=x.name)

@router.get('/risk/configuration')
def get_risk(u=Depends(auth), s: Session=Depends(db)):
    r = risk_for(s, u.id)
    s.commit()
    return {k: getattr(r, k) for k in ['max_quantity', 'max_order_value', 'max_daily_orders', 'max_daily_loss', 'max_positions', 'kill_switch']}

@router.put('/risk/configuration')
def set_risk(data: RiskInput, u=Depends(auth), s: Session=Depends(db)):
    r = risk_for(s, u.id)
    for k, v in data.model_dump().items():
        setattr(r, k, v)
    audit(s, u.id, 'risk_updated')
    s.commit()
    return {'message': 'Risk limits saved'}

@router.get('/orders')
def orders(u=Depends(auth), s: Session=Depends(db)):
    return [order_public(x) for x in s.scalars(select(Order).where(Order.user_id == u.id).order_by(Order.created_at.desc()).limit(200))]

@router.get('/orders/{record_id}')
def get_order(record_id: str, u=Depends(auth), s: Session=Depends(db)):
    return order_public(owned(s, Order, record_id, u.id))

@router.get('/positions')
def positions(u=Depends(auth), s: Session=Depends(db)):
    return [dict(id=x.id, symbol=x.symbol, quantity=x.quantity, average_price=str(x.average_price), realized_pnl=str(x.realized_pnl)) for x in s.scalars(select(Position).where(Position.user_id == u.id))]

@router.get('/positions/{record_id}')
def position(record_id: str, u=Depends(auth), s: Session=Depends(db)):
    x = owned(s, Position, record_id, u.id)
    return dict(id=x.id, symbol=x.symbol, quantity=x.quantity)

@router.post('/paper/orders', status_code=201)
def paper_order(data: PaperOrderInput, u=Depends(auth), s: Session=Depends(db)):
    if not settings.paper_trading_enabled:
        raise HTTPException(409, 'Paper trading disabled')
    r = risk_for(s, u.id)
    request_hash = digest(json.dumps(data.model_dump(mode='json'), sort_keys=True))
    previous = s.scalar(select(Order).where(Order.user_id == u.id, Order.idempotency_key == data.idempotency_key))
    if previous:
        if previous.request_hash != request_hash:
            raise HTTPException(409, 'Idempotency key reused with different request')
        return order_public(previous)
    owned(s, Strategy, data.strategy_id, u.id)
    platform = s.get(PlatformControl, 'global')
    if r.kill_switch or (platform and platform.kill_switch):
        raise HTTPException(409, 'Emergency stop active')
    if data.quantity > r.max_quantity or data.price * data.quantity > r.max_order_value:
        raise HTTPException(422, 'Order exceeds personal risk limits')
    midnight = now().replace(hour=0, minute=0, second=0, microsecond=0)
    count = s.scalar(select(func.count(Order.id)).where(Order.user_id == u.id, Order.created_at >= midnight))
    if count >= r.max_daily_orders:
        raise HTTPException(422, 'Daily order limit reached')
    all_positions = list(s.scalars(select(Position).where(Position.user_id == u.id)))
    daily_pnl = s.scalar(select(func.coalesce(func.sum(Order.realized_pnl), 0)).where(Order.user_id == u.id, Order.created_at >= midnight))
    if -daily_pnl >= r.max_daily_loss:
        raise HTTPException(422, 'Realized loss limit reached')
    p = next((x for x in all_positions if x.symbol == data.symbol), None)
    if data.side == 'SELL' and (not p or p.quantity < data.quantity):
        raise HTTPException(422, 'Paper simulator does not support short selling')
    if data.side == 'BUY' and (not p or p.quantity == 0) and (sum((x.quantity > 0 for x in all_positions)) >= r.max_positions):
        raise HTTPException(422, 'Position limit reached')
    if not p:
        p = Position(user_id=u.id, symbol=data.symbol, quantity=0, average_price=0, realized_pnl=0)
        s.add(p)
    realized = Decimal(0)
    if data.side == 'BUY':
        p.average_price = (p.average_price * p.quantity + data.price * data.quantity) / (p.quantity + data.quantity)
        p.quantity += data.quantity
    else:
        realized = (data.price - p.average_price) * data.quantity
        p.realized_pnl += realized
        p.quantity -= data.quantity
        if p.quantity == 0:
            p.average_price = 0
    o = Order(realized_pnl=realized, user_id=u.id, strategy_id=data.strategy_id, symbol=data.symbol, side=data.side, quantity=data.quantity, price=data.price, idempotency_key=data.idempotency_key, request_hash=request_hash)
    s.add(o)
    audit(s, u.id, 'paper_order_filled')
    s.commit()
    return order_public(o)

@router.post('/live/orders')
def live_order(data: LiveOrderInput, u=Depends(auth), s: Session=Depends(db)):
    account = owned(s, BrokerAccount, data.broker_account_id, u.id)
    strategy = owned(s, Strategy, data.strategy_id, u.id)
    from app.brokers.approval.approval_service import missing_requirements
    missing = missing_requirements(s, account.broker)
    raise HTTPException(409, {'message': 'No broker order submitted', 'runtime_blocker': 'Live execution and reconciliation unavailable', 'missing_requirements': missing, 'account_authorized': account.live_authorized, 'strategy_approved': strategy.approved})

@router.post('/risk/emergency-stop')
def user_switch(data: SwitchInput, u=Depends(auth), s: Session=Depends(db)):
    r = risk_for(s, u.id)
    r.kill_switch = data.enabled
    audit(s, u.id, 'user_stop:' + str(data.enabled))
    s.commit()
    return {'stopped': data.enabled, 'liquidated': False}

@router.post('/admin/emergency-stop')
def platform_switch(data: SwitchInput, u=Depends(admin), s: Session=Depends(db)):
    if u.role != 'SUPER_ADMIN':
        raise HTTPException(403, 'Super administrator required')
    p = s.get(PlatformControl, 'global')
    if not p:
        p = PlatformControl(id='global')
        s.add(p)
    p.kill_switch = data.enabled
    audit(s, u.id, 'platform_stop:' + str(data.enabled))
    s.commit()
    return {'stopped': data.enabled, 'liquidated': False}
