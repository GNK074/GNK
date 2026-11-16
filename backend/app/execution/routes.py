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
from app.compliance.service import require_disclosure
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
