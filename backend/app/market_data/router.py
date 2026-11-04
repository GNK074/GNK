"""Authenticated market-data APIs; no broker execution credentials are used."""
import asyncio,secrets
from datetime import date,datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,Request,Query
from sqlalchemy import select,func
from sqlalchemy.orm import Session
import jwt
from app.core.config import now,SECRET,digest,expired,settings
from app.database.session import db
from app.models.identity import User
from app.security.authentication import auth,admin
from app.services.accounts import audit
from app.api.users import session_id
from app.market_data.config import market_settings as cfg
from app.market_data.models import MarketInstrument,MarketSubscription,MarketEntitlement,MarketCandle,MarketSyncJob,MarketProviderSecret
from app.market_data.service import get_store,MarketDataService,instrument_public,provider
from app.market_data.subscription_manager import entitlement,available_instrument,subscribe,provider_status
from app.market_data.schemas import SubscribeInput,HistoryInput,EntitlementInput,INTERVALS
from app.market_data.providers.base import ProviderError
from app.market_data.providers.upstox.auth import synchronize_secret
from app.market_data.tasks.instrument_sync import enqueue_instruments
from app.market_data.tasks.historical_sync import enqueue_history
router=APIRouter(prefix='/api/v1/marketdata')
admin_router=APIRouter(prefix='/api/v1/admin/marketdata')

def limited(u):
    try:
        if not get_store().user_allowed(u.id):raise HTTPException(429,'Market-data request limit reached')
    except HTTPException:raise
    except Exception:raise HTTPException(503,'Market-data cache is unavailable') from None

def candle_public(c):
    result={k:getattr(c,k) for k in ('timestamp','exchange_timestamp','open','high','low','close','volume','oi','provider','source','quality')}
    if result['timestamp'].tzinfo is None:result['timestamp']=result['timestamp'].replace(tzinfo=timezone.utc)
    return result

def public_subscription(x):return {'id':x.id,'instrument_key':x.instrument_key,'mode':x.mode,'created':x.created}

def status_payload(s):
    row=provider_status(s)
    try:state=get_store().state()
    except Exception:state={'state':'CACHE_UNAVAILABLE'}
    state={**state,'provider':'upstox','enabled':cfg.upstox_enabled and row.enabled,'websocket_enabled':cfg.upstox_websocket_enabled,'distribution_approved':cfg.marketdata_distribution_approved and bool(cfg.marketdata_approval_reference.strip()),'approval_review_required':not cfg.marketdata_distribution_approved,'credentials_configured':bool(s.get(MarketProviderSecret,'upstox')),'execution_enabled':settings.live_trading_enabled,'timezone':'Asia/Kolkata','max_instruments':cfg.marketdata_max_instruments}
    if not state['enabled']:state['state']='DISABLED'
    return state

@router.get('/status')
def status(u=Depends(auth),s:Session=Depends(db)):return status_payload(s)
@router.get('/providers')
def providers(u=Depends(auth),s:Session=Depends(db)):return [status_payload(s)]
@router.get('/health')
def health(u=Depends(auth),s:Session=Depends(db)):
    state=status_payload(s)
    if state['enabled'] and state['state'] not in ('CONNECTED',):raise HTTPException(503,{'code':'MARKET_DATA_UNAVAILABLE','state':state['state']})
    return state

@router.get('/instruments')
@router.get('/instruments/search')
def instruments(q:str=Query(default='',max_length=100),exchange:str|None=None,segment:str|None=None,instrument_type:str|None=None,expiry:date|None=None,include_expired:bool=False,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0,le=100000),u=Depends(auth),s:Session=Depends(db)):
    limited(u);access=entitlement(s,u.id)
    allowed=set(access.segments)&cfg.segments
    statement=select(MarketInstrument).where(MarketInstrument.provider=='upstox',MarketInstrument.segment.in_(allowed))
    if q:statement=statement.where(MarketInstrument.symbol.ilike('%'+q.replace('%','').replace('_','')+'%') | MarketInstrument.name.ilike('%'+q.replace('%','').replace('_','')+'%'))
    if exchange:
        if exchange not in ('NSE','BSE'):raise HTTPException(422,'Choose NSE or BSE')
        statement=statement.where(MarketInstrument.exchange==exchange)
    if segment:statement=statement.where(MarketInstrument.segment==segment)
    if instrument_type:statement=statement.where(MarketInstrument.instrument_type==instrument_type)
    if expiry:statement=statement.where(MarketInstrument.expiry==expiry)
    if not include_expired:statement=statement.where(MarketInstrument.status=='ACTIVE')
    rows=list(s.scalars(statement.order_by(MarketInstrument.symbol,MarketInstrument.id).offset(offset).limit(limit+1)))
    return {'items':[instrument_public(x) for x in rows[:limit]],'has_more':len(rows)>limit,'offset':offset,'tick_size_units':'PROVIDER_ORIGINAL_NO_CONVERSION_ASSUMED'}

@router.get('/instruments/{instrument_id}')
def instrument(instrument_id:str,u=Depends(auth),s:Session=Depends(db)):
    limited(u);row=s.get(MarketInstrument,instrument_id)
    if not row:raise HTTPException(404,'Instrument not found')
    available_instrument(s,u.id,row.instrument_key,allow_expired=True)
    return instrument_public(row)

@router.get('/quotes')
def quotes(instrument_keys:str=Query(max_length=20000),mode:str='ltpc',u=Depends(auth),s:Session=Depends(db)):
    limited(u)
    try:return {'items':MarketDataService(s,u.id).quotes(instrument_keys.split(','),mode)}
    except ProviderError as error:raise HTTPException(503,error.code) from None
    except HTTPException:raise
    except Exception:raise HTTPException(503,'MARKET_DATA_UNAVAILABLE') from None

@router.get('/ohlc')
def ohlc(instrument_keys:str=Query(max_length=20000),u=Depends(auth),s:Session=Depends(db)):
    response=quotes(instrument_keys,'full',u,s)
    return {'items':[{key:value for key,value in row.items() if key in ('instrument_key','open','high','low','close','data_status','provider','source','received_at')} for row in response['items']]}

@router.get('/history')
@router.get('/intraday')
def history(request:Request,instrument_id:str,interval:str='1m',from_date:date|None=None,to_date:date|None=None,refresh:bool=False,limit:int=Query(1000,ge=1,le=5000),before:datetime|None=None,u=Depends(auth),s:Session=Depends(db)):
    limited(u)
    from zoneinfo import ZoneInfo
    today=now().astimezone(ZoneInfo('Asia/Kolkata')).date()
    intraday=request.url.path.endswith('/intraday')
    try:data=HistoryInput(instrument_id=instrument_id,interval=interval,from_date=today if intraday else from_date or today,to_date=today if intraday else to_date or today)
    except ValueError:raise HTTPException(422,'Invalid historical interval or dates') from None
    if intraday and INTERVALS[interval][0] in ('weeks','months'):raise HTTPException(422,'Intraday does not support weekly/monthly candles')
    row=s.get(MarketInstrument,instrument_id)
    if not row:raise HTTPException(404,'Instrument not found')
    available_instrument(s,u.id,row.instrument_key,allow_expired=not intraday)
    start=datetime.combine(data.from_date,datetime.min.time(),ZoneInfo('Asia/Kolkata')).astimezone(timezone.utc)
    from datetime import timedelta
    end=datetime.combine(data.to_date+timedelta(days=1),datetime.min.time(),ZoneInfo('Asia/Kolkata')).astimezone(timezone.utc)
    statement=select(MarketCandle).where(MarketCandle.instrument_id==row.id,MarketCandle.interval==interval,MarketCandle.timestamp>=start,MarketCandle.timestamp<end)
    if before:
        if before.tzinfo is None:raise HTTPException(422,'Cursor must include a timezone')
        statement=statement.where(MarketCandle.timestamp<before)
    candles=list(s.scalars(statement.order_by(MarketCandle.timestamp.desc()).limit(min(limit,cfg.marketdata_candle_response_limit)+1)))
    limit=min(limit,cfg.marketdata_candle_response_limit)
    more=len(candles)>limit;candles=candles[:limit]
    job=None
    if refresh:
        if not cfg.upstox_enabled or not provider_status(s).enabled:raise HTTPException(409,'Provider is disabled')
        job=enqueue_history(s,data.model_dump(mode='json'),u.id,intraday);s.commit()
    return {'instrument':instrument_public(row),'interval':interval,'timezone':'Asia/Kolkata','items':[candle_public(c) for c in reversed(candles)],'next_cursor':candle_public(candles[-1])['timestamp'] if more and candles else None,'sync':{'id':job.id,'state':job.state} if job else None,'gap_policy':'Provider gaps remain missing; no interpolation or synthetic candles.'}

@router.get('/subscriptions')
def subscriptions(u=Depends(auth),s:Session=Depends(db)):
    entitlement(s,u.id)
    return [public_subscription(row) for row in s.scalars(select(MarketSubscription).where(MarketSubscription.user_id==u.id))]
@router.post('/subscriptions')
def add_subscription(data:SubscribeInput,u=Depends(auth),s:Session=Depends(db)):
    limited(u);rows=subscribe(s,u.id,data.instrument_keys,data.mode);audit(s,u.id,'market_subscription_updated');s.commit();return [public_subscription(x) for x in rows]
@router.delete('/subscriptions/{subscription_id}')
def remove_subscription(subscription_id:str,u=Depends(auth),s:Session=Depends(db)):
    row=s.scalar(select(MarketSubscription).where(MarketSubscription.id==subscription_id,MarketSubscription.user_id==u.id))
    if not row:raise HTTPException(404,'Subscription not found')
    s.delete(row);audit(s,u.id,'market_subscription_deleted');s.commit();return {'message':'Subscription removed'}

@router.get('/sync-status')
def sync_status(u=Depends(auth),s:Session=Depends(db)):
    query=select(MarketSyncJob)
    if u.role not in ('ADMIN','SUPER_ADMIN'):query=query.where(MarketSyncJob.requested_by==u.id)
    return [{k:getattr(row,k) for k in ('id','kind','state','processed','error_code','created','started','finished')} for row in s.scalars(query.order_by(MarketSyncJob.created.desc()).limit(30))]

@router.post('/ws-ticket')
def ticket(request:Request,u=Depends(auth),s:Session=Depends(db)):
    limited(u);entitlement(s,u.id)
    claims=jwt.decode(request.cookies['access'],SECRET,algorithms=['HS256'],audience='gnk-web',issuer='gnk-api')
    raw=secrets.token_urlsafe(32)
    get_store().ticket(digest(raw),{'user_id':u.id,'session_id':claims['sid'],'access_expires':claims['exp']})
    return {'ticket':raw,'expires_in':30,'path':'/ws/v1/marketdata','protocol':'gnk.marketdata'}

@admin_router.post('/provider/enable')
def enable(u=Depends(admin),s:Session=Depends(db)):
    if u.role!='SUPER_ADMIN':raise HTTPException(403,'Super administrator required')
    if not cfg.upstox_enabled:raise HTTPException(409,'UPSTOX_ENABLED must be explicitly configured first')
    synchronize_secret(s)
    try:asyncio.run(provider(s,get_store()).health_check())
    except ProviderError as error:raise HTTPException(503,error.code) from None
    row=provider_status(s);row.enabled=True;row.updated=now();audit(s,u.id,'market_provider_enabled');s.commit()
    return status_payload(s)
@admin_router.post('/provider/disable')
def disable(u=Depends(admin),s:Session=Depends(db)):
    if u.role!='SUPER_ADMIN':raise HTTPException(403,'Super administrator required')
    row=provider_status(s);row.enabled=False;row.updated=now();audit(s,u.id,'market_provider_disabled');s.commit();return status_payload(s)
@admin_router.post('/instruments/sync',status_code=202)
def sync_instruments(u=Depends(admin),s:Session=Depends(db)):
    job=enqueue_instruments(s,u.id);audit(s,u.id,'market_instrument_sync_requested');s.commit();return {'job_id':job.id,'state':job.state}
@admin_router.post('/history/sync',status_code=202)
def sync_history(data:HistoryInput,u=Depends(admin),s:Session=Depends(db)):
    if not s.get(MarketInstrument,data.instrument_id):raise HTTPException(404,'Instrument not found')
    job=enqueue_history(s,data.model_dump(mode='json'),u.id);audit(s,u.id,'market_history_sync_requested');s.commit();return {'job_id':job.id,'state':job.state}
@admin_router.put('/users/{user_id}/access')
def set_access(user_id:str,data:EntitlementInput,u=Depends(admin),s:Session=Depends(db)):
    if u.role!='SUPER_ADMIN':raise HTTPException(403,'Super administrator required')
    if not s.get(User,user_id):raise HTTPException(404,'User not found')
    if not set(data.segments)<=cfg.segments or not set(data.modes)<=cfg.modes:raise HTTPException(422,'Access exceeds configured distribution scope')
    if data.expires_at and (data.expires_at.tzinfo is None or expired(data.expires_at)):raise HTTPException(422,'Access expiry must be a future timezone-aware timestamp')
    from app.market_data.models import MarketProviderStatus
    provider_status(s);s.scalar(select(MarketProviderStatus).where(MarketProviderStatus.provider=='upstox').with_for_update())
    row=s.get(MarketEntitlement,user_id)
    if data.enabled and (not row or not row.enabled):
        count=s.scalar(select(func.count()).select_from(MarketEntitlement).where(MarketEntitlement.enabled==True))
        if count>=cfg.marketdata_max_users:raise HTTPException(409,'Approved user capacity reached')
    if not row:row=MarketEntitlement(user_id=user_id);s.add(row)
    for key,value in data.model_dump().items():setattr(row,key,value)
    audit(s,u.id,'market_access_changed:'+user_id);s.commit();return {'user_id':row.user_id,'enabled':row.enabled,'segments':row.segments,'modes':row.modes,'max_instruments':row.max_instruments,'expires_at':row.expires_at}
