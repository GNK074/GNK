"""GNK-ticket authenticated private browser sockets; no broker tokens on clients."""
import asyncio,json,secrets,time
import jwt
from fastapi import APIRouter,Depends,HTTPException,Request,WebSocket
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from app.core.config import settings,SECRET,digest,expired
from app.database.session import db,DB
from app.database.tenancy import set_context
from app.security.authentication import auth,cache
from app.models.identity import User,LoginSession
from app.models.trading import BrokerAccount,BrokerCredential
from app.market_data.models import MarketInstrument
from app.portfolio.service import version
from .routes import account,client_for,output
from . import streams
router=APIRouter()

def proof(request,u,aid):
    claims=jwt.decode(request.cookies.get('access',''),SECRET,algorithms=['HS256'],audience='gnk-web',issuer='gnk-api')
    return dict(user_id=u.id,session_id=claims['sid'],account_id=aid,access_expires=claims['exp'])

class WatchInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    account_id:str
    instrument_ids:list[str]=Field(max_length=100)
    subscription_id:str=Field(default='',max_length=64,pattern=r'^[A-Za-z0-9_-]*$')

@router.post('/api/v1/dhan/stream/subscribe')
def subscribe(data:WatchInput,request:Request,u=Depends(auth),s=Depends(db)):
    if not settings.dhan_stream_enabled:raise HTTPException(409,'Private broker streams are disabled by the operator')
    client_for(s,u.id,data.account_id)
    items=[]
    for iid in set(data.instrument_ids):
        row=s.get(MarketInstrument,iid)
        if not row or row.provider!='dhan' or row.status!='ACTIVE':raise HTTPException(404,'Choose an active Dhan instrument from the synchronized master')
        parts=row.instrument_key.split('|')
        if len(parts)!=3 or parts[1] not in streams.SEGMENTS:raise HTTPException(422,'Unsupported private-stream instrument')
        items.append(dict(instrument_key=row.instrument_key,segment=parts[1],security_id=parts[2]))
    value=proof(request,u,data.account_id);value['instruments']=sorted(items,key=lambda r:r['instrument_key']);value['subscription_id']=data.subscription_id or secrets.token_hex(16)
    key=streams.watch_key(u.id,data.account_id)
    if items:cache.set(key,json.dumps(value),ex=600)
    elif data.subscription_id:
        cache.eval("local raw=redis.call('GET',KEYS[1]);if not raw then return 0 end;local v=cjson.decode(raw);if v.subscription_id==ARGV[1] then return redis.call('DEL',KEYS[1]) end;return 0",1,key,data.subscription_id)
    else:cache.delete(key)
    return {'subscription_id':value['subscription_id'],'subscribed':len(items),'expires_in':600,'refresh_before_seconds':120,'source':'GNK_PRIVATE_BROKER_STREAM'}

class TicketInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    account_id:str

@router.post('/api/v1/dhan/stream-ticket')
def ticket(data:TicketInput,request:Request,u=Depends(auth),s=Depends(db)):
    client_for(s,u.id,data.account_id)
    if not settings.dhan_stream_enabled:raise HTTPException(409,'Private broker streams are disabled')
    raw=secrets.token_urlsafe(32);cache.set('gnk:dhan:ticket:'+digest(raw),json.dumps(proof(request,u,data.account_id)),ex=30)
    return {'ticket':raw,'expires_in':30,'protocol':'gnk.dhan'}

def validate(proof):
    if time.time()>=proof['access_expires']:raise ValueError()
    with DB() as s:
        user=s.get(User,proof['user_id']);session=s.get(LoginSession,proof['session_id'])
        if not user or not user.active or not user.verified or not session or session.user_id!=user.id or session.revoked or not session.mfa_complete or expired(session.expires):raise ValueError()
        set_context(s,user.id)
        a=account(s,user.id,proof['account_id']);c=s.scalar(select(BrokerCredential).where(BrokerCredential.user_id==user.id,BrokerCredential.account_id==a.id))
        if a.status!='connected' or not c or not c.expires_at or expired(c.expires_at):raise ValueError()
        watch=cache.get(streams.watch_key(user.id,a.id));watch=json.loads(watch) if watch else {}
        values=[streams.latest(user.id,a.id,version(c),r['instrument_key']) for r in watch.get('instruments',[])]
        event=cache.get(streams.prefix(user.id,a.id)+':order')
        return {'type':'broker_update','ticks':values,'order_update':json.loads(event) if event else None,'connection':streams.status(user.id,a.id)}

@router.websocket('/ws/v1/dhan')
async def socket(ws:WebSocket):
    uid=None;cid=secrets.token_hex(12)
    try:
        if not settings.dhan_stream_enabled or ws.headers.get('origin','').rstrip('/') not in {x.rstrip('/') for x in settings.origins}:raise ValueError()
        protocols=[v.strip() for v in ws.headers.get('sec-websocket-protocol','').split(',')]
        if len(protocols)!=2 or protocols[0]!='gnk.dhan' or len(protocols[1])>100:raise ValueError()
        raw=await asyncio.to_thread(cache.getdel,'gnk:dhan:ticket:'+digest(protocols[1]))
        if not raw:raise ValueError()
        p=json.loads(raw);await asyncio.to_thread(validate,p);uid=p['user_id']
        slots='gnk:dhan:sockets:'+uid
        ok=cache.eval("redis.call('ZREMRANGEBYSCORE',KEYS[1],'-inf',ARGV[1]); if redis.call('ZCARD',KEYS[1])>=3 then return 0 end; redis.call('ZADD',KEYS[1],ARGV[2],ARGV[3]);redis.call('EXPIRE',KEYS[1],45);return 1",1,slots,time.time(),time.time()+30,cid)
        if not ok:raise ValueError()
    except Exception:
        await ws.close(code=1008);return
    await ws.accept(subprotocol='gnk.dhan')
    try:
        while True:
            data=await asyncio.to_thread(validate,p)
            # Never disclose lease tokens or credential fingerprints to the browser.
            state=data['connection'];data['connection']={k:state.get(k) for k in ('market_connected','order_connected')}
            await asyncio.wait_for(ws.send_json(data),timeout=3)
            cache.zadd(slots,{cid:time.time()+30})
            await asyncio.sleep(1)
    except Exception:pass
    finally:
        try:cache.zrem(slots,cid)
        except Exception:pass
        try:await ws.close(code=1000)
        except Exception:pass
