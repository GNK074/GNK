from fastapi import Depends,APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.security.authentication import auth
from app.database.session import db
from app.models.trading import Strategy
from app.brokers.gateway import connections
router=APIRouter()
@router.get('/api/v1/dashboard')
def dashboard(u=Depends(auth),s:Session=Depends(db)):
    accounts=connections(u,s)
    count=sum(a['status']=='connected' for a in accounts)
    strategies=[{'id':x.id,'name':x.name,'approved':x.approved} for x in s.scalars(select(Strategy).where(Strategy.user_id==u.id))]
    from app.execution import live_service as live
    live_ready=live.enabled() and live.broker_approved(s) and live.worker_ready()
    from app.portfolio.service import summary as portfolio_summary,serialized
    portfolio=serialized(portfolio_summary(s,u.id))
    return {'mode':'broker_connected' if count else 'disconnected','live_trading':live_ready,'connections':count,'broker_accounts':accounts,'portfolio':portfolio,'strategies':strategies,'market_data':None,'connection_scope':'live_placement_gated' if live_ready else 'identity_validation_only'}
