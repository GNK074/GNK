"""Owner-only Dhan SDK account and research APIs; separate from execution."""
from datetime import date,timedelta,timezone
from typing import Literal
from decimal import Decimal
import json,hashlib,csv,io
from fastapi import APIRouter,Depends,HTTPException,Query,Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field,model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import now,expired,settings
from app.database.session import db
from app.models.trading import BrokerAccount,BrokerCredential
from app.security.authentication import auth,admin,cache
from app.security.ownership import owned
from app.security.encryption import open_credentials,seal_credentials
from app.services.accounts import audit
from app.portfolio.models import PortfolioSync
from app.portfolio.service import serialized,version,public_accounts
from app.portfolio.adapters import normalize
from .client import DhanClient,DhanError,SDK_VERSION
from .analytics import candles,aggregate,indicators
router=APIRouter(prefix='/api/v1/dhan',tags=['GNK Dhan integration'])
SEGMENTS=Literal['NSE_EQ','BSE_EQ','NSE_FNO','BSE_FNO','NSE_CURRENCY','BSE_CURRENCY','MCX_COMM','IDX_I']

def safe_number(value):
    if value is None or isinstance(value,bool):return None
    try:
        number=Decimal(str(value))
        return number if number.is_finite() else None
    except Exception:return None

def safe_leg(value):
    if not isinstance(value,dict):return {}
    keys=('security_id','last_price','oi','previous_oi','volume','implied_volatility','top_bid_price','top_bid_quantity','top_ask_price','top_ask_quantity')
    result={k:safe_number(value.get(k)) for k in keys}
    greeks=value.get('greeks',{})
    result['greeks']={k:safe_number(greeks.get(k)) for k in ('delta','theta','gamma','vega')} if isinstance(greeks,dict) else {}
    return result

def safe_quote(value):
    if not isinstance(value,dict):return {}
    result={k:safe_number(value.get(k)) for k in ('last_price','volume','oi','average_price','buy_quantity','sell_quantity','upper_circuit_limit','lower_circuit_limit')}
    ohlc=value.get('ohlc',{})
    result['ohlc']={k:safe_number(ohlc.get(k)) for k in ('open','high','low','close')} if isinstance(ohlc,dict) else {}
    depth=value.get('depth',{})
    result['depth']={side:[{k:safe_number(r.get(k)) for k in ('price','quantity','orders')} for r in depth.get(side,[])[:20] if isinstance(r,dict)] for side in ('buy','sell')} if isinstance(depth,dict) else {}
    return result

def scalar(value):return str(value)[:200] if isinstance(value,(str,int,bool)) else None

def mask(value):return '••••'+str(value or '')[-4:]
def output(data):return JSONResponse(jsonable_encoder(serialized(data)))
def account(s,uid,aid):
    a=owned(s,BrokerAccount,aid,uid)
    if a.broker!='dhan':raise HTTPException(404,'Dhan account not found')
    return a

def client_for(s,uid,aid):
    a=account(s,uid,aid)
    c=s.scalar(select(BrokerCredential).where(BrokerCredential.user_id==uid,BrokerCredential.account_id==aid))
    if a.status!='connected' or not c or not c.expires_at or expired(c.expires_at):raise HTTPException(409,'Dhan session expired or disconnected. Reconnect in Brokers & exchanges.')
    try:
        envelope=open_credentials(uid,aid,c.ciphertext);data=envelope.get('credentials',envelope)
        client=DhanClient(a.account_identifier,data['access_token'])
    except Exception:raise HTTPException(409,'Dhan credentials could not be loaded. Reconnect this account.') from None
    return a,c,client

def read(s,uid,aid,operation,params,call,ttl=15):
    a,c,client=client_for(s,uid,aid)
    digest=hashlib.sha256(json.dumps([params,version(c)],sort_keys=True).encode()).hexdigest()
    key=f'gnk:dhan:data:{uid}:{aid}:{operation}:{digest}'
    try:
        cached=cache.get(key)
        if cached:return json.loads(cached)
        if not cache.set(key+':busy','1',nx=True,ex=15):raise HTTPException(429,'This Dhan request is already running. Try again shortly.')
    except HTTPException:raise
    except Exception:raise HTTPException(503,'Dhan data cache unavailable') from None
    try:
        data=call(client)
        result=serialized(dict(data=data,source='DHAN_SDK',sdk_version=SDK_VERSION,fetched_at=now().isoformat(),data_status='BROKER_SNAPSHOT'))
        cache.set(key,json.dumps(result),ex=ttl)
        return result
    except DhanError as error:raise HTTPException(409,error.code) from None
    except Exception:raise HTTPException(502,'INVALID_DHAN_RESPONSE') from None
    finally:
        try:cache.delete(key+':busy')
        except Exception:pass

@router.get('/status')
def status(u=Depends(auth),s:Session=Depends(db)):
    accounts=public_accounts(s,u.id,broker='dhan')
    for a in accounts:a['account']=mask(a['account'])
    return output(dict(sdk_version=SDK_VERSION,accounts=accounts,portfolio=True,profile=True,token_renewal=True,quotes=True,option_chain=True,historical=True,trade_history=True,technical_research=True,live_dhan_execution=bool(settings.trading_enabled and settings.live_trading_enabled and settings.dhan_execution_enabled),live_feed=settings.dhan_stream_enabled,oauth=settings.dhan_oauth_enabled,master_sync_allowed=u.role=='SUPER_ADMIN',ml_model='NOT_CONFIGURED',execution_note='Dhan NSE equity intraday LIMIT/DAY uses GNK intent, account approval, risk and REST fill reconciliation gates. Private feeds require your own connected account.'))

@router.get('/profile')
def profile(account_id:str,u=Depends(auth),s:Session=Depends(db)):
    def load(client):
        d=client.profile()
        if not isinstance(d,dict):raise DhanError('INVALID_DHAN_RESPONSE')
        return dict(client_id=mask(d.get('dhanClientId')),token_validity=scalar(d.get('tokenValidity')),data_plan=scalar(d.get('dataPlan')),data_validity=scalar(d.get('dataValidity')))
    return output(read(s,u.id,account_id,'profile',{},load,30))

@router.post('/accounts/{aid}/renew')
def renew(aid:str,u=Depends(auth),s:Session=Depends(db)):
    a=owned(s,BrokerAccount,aid,u.id,lock=True)
    if a.broker!='dhan':raise HTTPException(404,'Dhan account not found')
    a,c,client=client_for(s,u.id,aid)
    try:
        fresh=client.renew()
        token=fresh.get('accessToken') if isinstance(fresh,dict) else None
        if not isinstance(token,str) or not token:raise DhanError('DHAN_RENEWAL_REJECTED')
        from app.brokers.individual.verifiers import DhanVerifier
        verified=DhanVerifier().validate({'client_id':a.account_identifier,'access_token':token})
        if verified.account_identifier!=a.account_identifier:raise DhanError('DHAN_IDENTITY_MISMATCH')
        c.ciphertext=seal_credentials(u.id,aid,{'credentials':verified.credentials,'connection_method':'individual_credentials','verified_at':now().isoformat(),'expiry_basis':verified.expiry_basis})
        c.expires_at=verified.expires_at;c.key_version=settings.encryption_key_version
        from app.portfolio.service import connected
        connected(s,u.id,aid,'dhan')
        audit(s,u.id,'dhan_session_renewed:'+aid);s.commit()
        return {'message':'Dhan session renewed and portfolio refresh scheduled.','expires_at':verified.expires_at}
    except Exception as error:
        s.rollback()
        raise HTTPException(409,error.code if isinstance(error,DhanError) else 'Dhan renewal could not be verified. Reconnect if the previous token no longer works.') from None

class QuoteInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    account_id:str
    segment:SEGMENTS
    security_ids:list[int]=Field(min_length=1,max_length=50)
    mode:Literal['ltp','ohlc','full']='ltp'
    @model_validator(mode='after')
    def valid_ids(self):
        if any(v<=0 for v in self.security_ids) or len(set(self.security_ids))!=len(self.security_ids):raise ValueError('Use distinct positive Dhan security IDs')
        return self

@router.post('/quotes')
def quotes(data:QuoteInput,u=Depends(auth),s:Session=Depends(db)):
    def load(client):
        result=client.quote({data.segment:data.security_ids},data.mode)
        if not isinstance(result,dict) or not isinstance(result.get(data.segment),dict):raise DhanError('INVALID_DHAN_RESPONSE')
        allowed=('last_price','ohlc','volume','oi','depth','average_price','buy_quantity','sell_quantity','last_trade_time','upper_circuit_limit','lower_circuit_limit')
        return [{'security_id':str(i),'segment':data.segment,**safe_quote(result[data.segment].get(str(i),{}))} for i in data.security_ids]
    return output(read(s,u.id,data.account_id,'quotes',data.model_dump(),load,5))

@router.get('/expiries')
def expiries(account_id:str,security_id:int=Query(gt=0),segment:SEGMENTS='IDX_I',u=Depends(auth),s:Session=Depends(db)):
    def load(client):
        d=client.expiries(security_id,segment)
        if not isinstance(d,list) or len(d)>100 or any(not isinstance(v,str) or len(v)!=10 for v in d):raise DhanError('INVALID_DHAN_RESPONSE')
        return d
    return output(read(s,u.id,account_id,'expiries',{'security_id':security_id,'segment':segment},load,60))

@router.get('/option-chain')
def options(account_id:str,security_id:int=Query(gt=0),segment:SEGMENTS='IDX_I',expiry:date=Query(...),u=Depends(auth),s:Session=Depends(db)):
    def load(client):
        d=client.options(security_id,segment,expiry.isoformat())
        if not isinstance(d,dict) or not isinstance(d.get('oc'),dict) or len(d['oc'])>2000:raise DhanError('INVALID_DHAN_RESPONSE')
        allowed=('security_id','last_price','oi','previous_oi','volume','implied_volatility','top_bid_price','top_bid_quantity','top_ask_price','top_ask_quantity','greeks')
        rows=[]
        for strike,legs in d['oc'].items():
            try:value=Decimal(str(strike))
            except Exception:raise DhanError('INVALID_DHAN_RESPONSE') from None
            if not value.is_finite() or not isinstance(legs,dict):raise DhanError('INVALID_DHAN_RESPONSE')
            rows.append(dict(strike=value,**{side:safe_leg(legs.get(side,{})) for side in ('ce','pe')}))
        rows.sort(key=lambda r:r['strike'])
        def total(side):
            vals=[r[side].get('oi') for r in rows]
            if any(v is None for v in vals):return None
            return sum((Decimal(str(v)) for v in vals),Decimal(0))
        ce=total('ce');pe=total('pe')
        return {'underlying_price':safe_number(d.get('last_price')),'items':rows,'pcr':pe/ce if pe is not None and ce else None}
    return output(read(s,u.id,account_id,'options',{'security_id':security_id,'segment':segment,'expiry':str(expiry)},load,3))

@router.get('/history')
def history(account_id:str,security_id:int=Query(gt=0),segment:SEGMENTS='NSE_EQ',instrument:Literal['EQUITY','INDEX','FUTIDX','FUTSTK','OPTIDX','OPTSTK','FUTCUR','OPTCUR','FUTCOM','OPTFUT']='EQUITY',from_date:date=Query(...),to_date:date=Query(...),interval:Literal['1','2','3','5','15','25','30','60','D']='1',u=Depends(auth),s:Session=Depends(db)):
    if to_date<from_date or (to_date-from_date).days>90 or to_date>now().date():raise HTTPException(422,'Use a past date range of at most 90 days')
    if interval in ('2','3','30') and segment not in ('NSE_EQ','BSE_EQ','NSE_FNO','BSE_FNO','IDX_I'):raise HTTPException(422,'Derived intervals currently support NSE/BSE sessions only')
    def load(client):
        base='15' if interval=='30' else '1' if interval in ('2','3') else interval
        data=candles(client.history(str(security_id),segment,instrument,from_date.isoformat(),to_date.isoformat(),base))
        if interval in ('2','3','30'):data=aggregate(data,int(interval),int(base))
        return {'candles':data,'interval':interval,'derived':interval in ('2','3','30'),'research':indicators(data)}
    return output(read(s,u.id,account_id,'history',{'security_id':security_id,'segment':segment,'instrument':instrument,'from':str(from_date),'to':str(to_date),'interval':interval},load,60))

@router.get('/trade-history')
def trade_history(account_id:str,from_date:date,to_date:date,page:int=Query(0,ge=0,le=999),symbol:str='',side:Literal['','BUY','SELL']='',u=Depends(auth),s:Session=Depends(db)):
    if to_date<from_date or (to_date-from_date).days>90:raise HTTPException(422,'Use a date range of at most 90 days')
    def load(client):
        data=normalize('dhan','trades',client.trade_history(str(from_date),str(to_date),page))
        return [r for r in data if (not symbol or symbol.casefold() in r['symbol'].casefold()) and (not side or r['side']==side)]
    return output(read(s,u.id,account_id,'trades',{'from':str(from_date),'to':str(to_date),'page':page,'symbol':symbol,'side':side},load,30))

@router.get('/instruments')
def instruments(q:str=Query('',max_length=100),u=Depends(auth),s:Session=Depends(db)):
    from app.market_data.models import MarketInstrument
    statement=select(MarketInstrument).where(MarketInstrument.provider=='dhan',MarketInstrument.status=='ACTIVE',MarketInstrument.segment=='NSE_EQ')
    if q.strip():statement=statement.where(MarketInstrument.symbol.ilike('%'+q.strip().replace('%','').replace('_','')+'%'))
    rows=s.scalars(statement.order_by(MarketInstrument.symbol).limit(50))
    return output({'items':[{k:getattr(r,k) for k in ('id','instrument_key','symbol','segment','tick_size','lot_size','synced_at')} for r in rows]})

@router.post('/instruments/sync')
def sync_instruments(u=Depends(admin),s:Session=Depends(db)):
    if u.role!='SUPER_ADMIN':raise HTTPException(403,'Super administrator required')
    from .instruments import download,store
    try:
        rows=download();count=store(s,rows);audit(s,u.id,'dhan_instrument_master_synced:'+str(count));s.commit()
        return {'imported':count,'scope':'NSE/BSE unit-lot equity','version':rows[0]['version']}
    except DhanError as e:s.rollback();raise HTTPException(409,e.code) from None
