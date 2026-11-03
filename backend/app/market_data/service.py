import asyncio
from datetime import datetime,timezone
from fastapi import HTTPException
from sqlalchemy import select
from app.security.authentication import cache
from app.market_data.config import market_settings as cfg
from app.market_data.redis_store import RedisStore
from app.market_data.models import MarketInstrument,MarketTickLatest
from app.market_data.providers.upstox.auth import provider_token
from app.market_data.providers.upstox.provider import UpstoxProvider
from app.market_data.normalizer import normalize_quote
from app.market_data.market_calendar import quality,market_session
from app.market_data.subscription_manager import available_instrument,entitlement,provider_status
from app.market_data.providers.base import ProviderError

def get_store():return RedisStore(cache)

def provider(s,store):return UpstoxProvider(provider_token(s),store)

def instrument_public(row):
    return {key:getattr(row,key) for key in ('id','provider','instrument_key','exchange','segment','symbol','name','instrument_type','expiry','strike','lot_size','tick_size','underlying','status','version','synced_at')}

class MarketDataService:
    def __init__(self,s,user_id,store=None):self.s=s;self.user_id=user_id;self.store=store or get_store()
    def quotes(self,keys,mode="ltpc"):
        if not keys or len(keys)>100:raise HTTPException(422,'Request 1–100 instrument keys')
        known={key:available_instrument(self.s,self.user_id,key,mode) for key in dict.fromkeys(keys)}
        state=self.store.state();status=provider_status(self.s)
        connected=cfg.upstox_enabled and status.enabled and state.get('state')=='CONNECTED'
        result={};missing=[]
        for key,row in known.items():
            tick=self.store.latest(key)
            if tick:result[key]=quality(tick,connected,market_session(row.segment,{'segments':state.get('segments',{}),'received_at':state.get('updated_at')}))
            else:missing.append(key)
        if missing and cfg.upstox_enabled and status.enabled:
            raw=asyncio.run(provider(self.s,self.store).get_quotes(missing))
            for item in raw.values():
                key=item.get('instrument_token')
                if key in known and key in missing:
                    tick=normalize_quote(key,item,known[key].symbol)
                    result[key]=quality(tick,True,market_session(known[key].segment,{'segments':state.get('segments',{}),'received_at':state.get('updated_at')}))
        for key in missing:
            if key not in result:
                snapshot=self.s.get(MarketTickLatest,key)
                if snapshot and snapshot.expires_at.replace(tzinfo=timezone.utc)>datetime.now(timezone.utc):
                    result[key]=quality(snapshot.payload,False)
                else:
                    result[key]={'provider':'upstox','instrument_key':key,'symbol':known[key].symbol,'ltp':None,'data_status':'MISSING','received_at':None}
        return [filter_mode(tick,mode) for tick in result.values()]
    def require_live_quote(self,key):
        """Common strategy/AI/quant boundary: never returns snapshots or stale data as live."""
        tick=self.quotes([key])[0]
        if tick['data_status']!='LIVE':raise ProviderError('FRESH_MARKET_DATA_REQUIRED')
        return tick


def filter_mode(tick,mode):
    result=dict(tick)
    if mode=='ltpc':
        for name in ('volume','average_price','open','high','low','oi'):result[name]=None
        result['bid']=[];result['ask']=[];result['greeks']={}
    elif mode=='option_greeks':
        for name in ('average_price','open','high','low'):result[name]=None
        result['bid']=result.get('bid',[])[:1];result['ask']=result.get('ask',[])[:1]
    result['mode']=mode
    return result
