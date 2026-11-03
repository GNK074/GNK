from datetime import datetime,timezone
from fastapi import HTTPException
from sqlalchemy import select,func
from app.core.config import now,expired
from app.models.identity import User
from app.market_data.config import market_settings as cfg
from app.market_data.models import MarketProviderStatus,MarketEntitlement,MarketInstrument,MarketSubscription

def provider_status(s):
    row=s.get(MarketProviderStatus,'upstox')
    if not row:
        row=MarketProviderStatus(provider='upstox');s.add(row);s.flush()
    return row

def distribution_guard():
    if not cfg.marketdata_distribution_approved or not cfg.marketdata_approval_reference.strip():
        raise HTTPException(403,'Market-data distribution approval has not been independently verified')

def entitlement(s,user_id,mode=None):
    distribution_guard()
    item=s.get(MarketEntitlement,user_id)
    if not item or not item.enabled or (item.expires_at and expired(item.expires_at)):
        raise HTTPException(403,'Market-data access has not been granted to this account')
    if mode and (mode not in item.modes or mode not in cfg.modes):raise HTTPException(403,'Feed mode is not permitted')
    return item

def available_instrument(s,user_id,key,mode=None,allow_expired=False):
    allowed=entitlement(s,user_id,mode)
    instrument=s.scalar(select(MarketInstrument).where(MarketInstrument.instrument_key==key))
    if not instrument:raise HTTPException(404,'Instrument is not available in the synchronized master')
    if instrument.segment not in allowed.segments or instrument.segment not in cfg.segments:raise HTTPException(403,'Instrument segment is not permitted')
    if not allow_expired and instrument.status!='ACTIVE':raise HTTPException(409,'Instrument is not active for live subscription')
    if mode=='option_greeks' and instrument.instrument_type not in ('CE','PE'):raise HTTPException(422,'Option Greeks requires an option instrument')
    return instrument

def subscribe(s,user_id,keys,mode):
    allowed=entitlement(s,user_id,mode)
    # Global provider lock serializes capacity checks across concurrent users.
    status=provider_status(s)
    s.scalar(select(MarketProviderStatus).where(MarketProviderStatus.provider=='upstox').with_for_update())
    if not cfg.upstox_enabled or not status.enabled:raise HTTPException(409,'Market-data provider is disabled')
    keys=set(keys)
    for key in keys:available_instrument(s,user_id,key,mode)
    existing=list(s.scalars(select(MarketSubscription).where(MarketSubscription.user_id==user_id)))
    own={row.instrument_key:row for row in existing}
    if len(set(own)|keys)>min(allowed.max_instruments,cfg.marketdata_per_user_limit):raise HTTPException(422,'Personal subscription limit exceeded')
    # Worker flag is internal-only and never derived from request parameters.
    from app.database.tenancy import set_market_worker
    set_market_worker(s)
    global_keys=set(active_provider_subscriptions(s))
    s.info['market_worker']=False
    if s.get_bind().dialect.name=='postgresql':
        from sqlalchemy import text
        s.execute(text("SELECT set_config('app.market_worker','false',true)"))
    if len(global_keys|keys)>cfg.marketdata_max_instruments:raise HTTPException(422,'Provider subscription capacity reached')
    for key in keys:
        if key in own:own[key].mode=mode
        else:s.add(MarketSubscription(user_id=user_id,instrument_key=key,mode=mode))
    s.flush()
    return list(s.scalars(select(MarketSubscription).where(MarketSubscription.user_id==user_id)))


def active_provider_subscriptions(s):
    from app.database.tenancy import set_market_worker
    set_market_worker(s)
    rows=s.execute(select(MarketSubscription,MarketEntitlement,MarketInstrument,User.active,User.verified).join(MarketEntitlement,MarketEntitlement.user_id==MarketSubscription.user_id).join(User,User.id==MarketSubscription.user_id).join(MarketInstrument,MarketInstrument.instrument_key==MarketSubscription.instrument_key))
    desired={};ranks={'ltpc':0,'option_greeks':1,'full':2}
    for sub,access,instrument,active,verified in rows:
        if not access.enabled or not active or not verified or (access.expires_at and expired(access.expires_at)):continue
        if not instrument or instrument.status!='ACTIVE' or instrument.segment not in cfg.segments or instrument.segment not in access.segments or sub.mode not in access.modes or sub.mode not in cfg.modes:continue
        prior=desired.get(sub.instrument_key,'ltpc')
        desired[sub.instrument_key]=max((prior,sub.mode),key=lambda x:ranks[x])
    return dict(list(sorted(desired.items()))[:cfg.marketdata_max_instruments])
