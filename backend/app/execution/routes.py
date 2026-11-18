from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.database.session import db
from app.models.identity import User
from app.models.trading import RiskConfiguration, PlatformControl
from app.schemas.trading import RiskInput, SwitchInput
from app.security.authentication import auth, admin
from app.services.accounts import audit
router = APIRouter(prefix='/api/v1')


def risk_for(s, uid):
    if s.get_bind().dialect.name == 'sqlite':
        # SQLite ignores FOR UPDATE. Acquire the write lock before reading risk state.
        s.execute(update(User).where(User.id == uid).values(id=User.id))
    else:
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
