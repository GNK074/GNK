from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.session import db
from app.database.tenancy import set_context
from app.models.trading import BrokerAccount,Strategy
from app.execution.models import LiveOrder
from app.execution import live_service as live
from app.execution.upstox import ExecutionError
from app.security.authentication import auth,admin
from app.security.ownership import owned
from app.services.accounts import audit
from app.core.config import now
router=APIRouter(prefix='/api/v1/live')
admin_router=APIRouter(prefix='/api/v1/admin/live')
class ArmInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmation:Literal['ENABLE LIVE UPSTOX','ENABLE LIVE DHAN']
class GrantInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    user_id:str
    enabled:bool
    strategy_ids:list[str]=Field(default_factory=list,max_length=20)

def handle(error):raise HTTPException(409,error.code) from None
@router.get('/readiness')
def readiness(broker:Literal['upstox','dhan']='upstox',u=Depends(auth),s:Session=Depends(db)):
    from .readiness import snapshot
    return snapshot(s,u.id,broker)
@router.get('/orders')
def orders(u=Depends(auth),s:Session=Depends(db)):
    return [live.public(x) for x in s.scalars(select(LiveOrder).where(LiveOrder.user_id==u.id).order_by(LiveOrder.created_at.desc()).limit(200))]
@router.get('/positions/{account_id}')
def positions(account_id:str,u=Depends(auth),s:Session=Depends(db)):
    a=owned(s,BrokerAccount,account_id,u.id)
    try:
        broker=live.client(s,a);broker.verify_identity(a.account_identifier);rows=broker.positions()
        fields=('instrument_token','trading_symbol','product','quantity','average_price','last_price','realised','unrealised')
        return {'as_of':now(),'items':[{k:p.get(k) for k in fields} for p in rows]}
    except ExecutionError as error:handle(error)
@router.post('/accounts/{account_id}/arm')
def arm(account_id:str,data:ArmInput,u=Depends(auth),s:Session=Depends(db)):
    a=owned(s,BrokerAccount,account_id,u.id,lock=True)
    if data.confirmation!='ENABLE LIVE '+a.broker.upper():raise HTTPException(422,'Confirmation must name the selected broker')
    if not (live.enabled(a.broker) if a.broker=='dhan' else live.enabled()) or not (live.broker_approved(s,a.broker) if a.broker=='dhan' else live.broker_approved(s)) or not live.worker_ready() or not a.live_authorized:live.fail('Server, production approval, reconciliation and account authorization must be ready')
    try:live.client(s,a).verify_identity(a.account_identifier)
    except ExecutionError as error:handle(error)
    a.kill_switch=False;audit(s,u.id,'live_account_armed:'+a.id);s.commit();return {'armed':True}
@router.post('/accounts/{account_id}/disarm')
def disarm(account_id:str,u=Depends(auth),s:Session=Depends(db)):
    a=owned(s,BrokerAccount,account_id,u.id,lock=True);a.kill_switch=True
    audit(s,u.id,'live_account_disarmed:'+a.id);s.commit();return {'armed':False,'existing_broker_orders_cancelled':False}
@router.post('/orders/{order_id}/reconcile')
def reconcile(order_id:str,u=Depends(auth),s:Session=Depends(db)):
    row=owned(s,LiveOrder,order_id,u.id);a=owned(s,BrokerAccount,row.account_id,u.id,lock=True)
    try:live.reconcile(s,a,row)
    except ExecutionError as error:row.error_code=error.code;row.status=row.status if row.status in live.TERMINAL else 'RECONCILE_REQUIRED'
    audit(s,u.id,'live_order_reconciled:'+row.id);s.commit();return live.public(row)
@router.post('/orders/{order_id}/cancel')
def cancel(order_id:str,u=Depends(auth),s:Session=Depends(db)):
    row=owned(s,LiveOrder,order_id,u.id);a=owned(s,BrokerAccount,row.account_id,u.id,lock=True)
    # Cancellation remains available when placement flags or kill switches are off.
    try:
        broker=live.client(s,a);live.reconcile(s,a,row,broker)
        if row.status in live.TERMINAL:s.commit();return live.public(row)
        if not row.provider_order_id or row.status=='RECONCILE_REQUIRED':live.fail('Resolve the order identity before cancellation')
        row.status='CANCEL_PENDING';row.updated_at=now();s.commit()
        a=owned(s,BrokerAccount,a.id,u.id,lock=True)
        broker.cancel(row.provider_order_id)
    except ExecutionError as error:
        row.error_code=error.code;row.status=row.status if row.status in live.TERMINAL else 'RECONCILE_REQUIRED'
    audit(s,u.id,'live_cancel_requested:'+row.id);s.commit();return live.public(row)
@admin_router.put('/accounts/{account_id}/authorization')
def authorize(account_id:str,data:GrantInput,u=Depends(admin),s:Session=Depends(db)):
    if u.role!='SUPER_ADMIN':raise HTTPException(403,'Super administrator required')
    set_context(s,data.user_id)
    a=owned(s,BrokerAccount,account_id,data.user_id,lock=True)
    if a.broker not in ('upstox','dhan'):live.fail('Execution is not implemented for this broker')
    if data.enabled and not (live.broker_approved(s,a.broker) if a.broker=='dhan' else live.broker_approved(s)):live.fail('Selected broker production approval is required')
    strategies=[owned(s,Strategy,sid,data.user_id,lock=True) for sid in set(data.strategy_ids)]
    a.live_authorized=data.enabled;a.kill_switch=True
    for strategy in strategies:strategy.approved=data.enabled
    audit(s,u.id,'live_authorization:'+a.id+':'+str(data.enabled));s.commit()
    return {'account_id':a.id,'authorized':a.live_authorized,'armed':False}
