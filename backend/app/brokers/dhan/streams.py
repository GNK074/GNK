"""Private account streams: SDK market parser, sanitized order updates, Redis fencing."""
import asyncio,json,time,uuid,struct,logging,re
from datetime import datetime,timezone
from decimal import Decimal
from urllib.parse import urlencode
import websockets
from dhanhq import MarketFeed,OrderUpdate
from sqlalchemy import select,delete
from app.core.config import now,expired,settings
from app.database.session import DB
from app.database.tenancy import set_context
from app.models.identity import User,LoginSession
from app.models.trading import BrokerAccount,BrokerCredential
from app.execution.models import LiveOrder
from app.portfolio.service import version,serialized
from app.security.encryption import open_credentials
from app.security.authentication import cache
from .client import DhanClient,DhanError
from .instruments import key
HEARTBEAT='gnk:dhan:stream:heartbeat'
_SOCKET_LOG=logging.getLogger('gnk.private.broker.transport')
_SOCKET_LOG.disabled=True
_SOCKET_LOG.propagate=False
SEGMENTS={'IDX_I':0,'NSE_EQ':1,'NSE_FNO':2,'NSE_CURRENCY':3,'BSE_EQ':4,'MCX_COMM':5,'BSE_CURRENCY':7,'BSE_FNO':8}
REVERSE={v:k for k,v in SEGMENTS.items()}

def prefix(uid,aid):return f'gnk:dhan:private:{uid}:{aid}'
def lease_key(uid,aid):return prefix(uid,aid)+':lease'
def watch_key(uid,aid):return prefix(uid,aid)+':watch'
def status(uid,aid):
    fields=cache.hgetall(prefix(uid,aid)+':status')
    return {(k.decode() if isinstance(k,bytes) else k):(v.decode() if isinstance(v,bytes) else v) for k,v in fields.items()}
def fenced(uid,aid,owner,script,*args):return cache.eval("if redis.call('GET',KEYS[1])~=ARGV[1] then return 0 end "+script,1,lease_key(uid,aid),owner,*args)
def connection(uid,aid,owner,fingerprint,field,value):
    return fenced(uid,aid,owner,"redis.call('HSET',ARGV[2],ARGV[3],ARGV[4],'version',ARGV[5],'owner',ARGV[1]);redis.call('EXPIRE',ARGV[2],45);return 1",prefix(uid,aid)+':status',field,str(int(value)),fingerprint)
def packet(raw,parsed):
    if not isinstance(raw,bytes) or len(raw)<16 or not isinstance(parsed,dict) or raw[0] not in (2,4,8):return None
    if len(raw)<{2:16,4:50,8:162}[raw[0]]:return None
    stamp=int.from_bytes(raw[12:16] if raw[0]==2 else raw[14:18],'little')
    try:price=Decimal(str(parsed['LTP']));segment=REVERSE[int(parsed['exchange_segment'])];sid=str(int(parsed['security_id']))
    except Exception:return None
    if not price.is_finite() or price<=0 or stamp>time.time()+5:return None
    fields={k:parsed[k] for k in ('open','high','low','close','volume','OI','depth','avg_price','total_sell_quantity','total_buy_quantity') if k in parsed}
    return dict(instrument_key=key(segment,sid),segment=segment,security_id=sid,ltp=str(price),exchange_timestamp=stamp,received_at=time.time(),source='DHAN_PRIVATE_WEBSOCKET',**fields)
def publish(uid,aid,owner,value):
    return fenced(uid,aid,owner,"redis.call('SET',ARGV[2],ARGV[3],'EX',60);return 1",prefix(uid,aid)+':tick:'+value['instrument_key'],json.dumps(serialized(dict(value,_owner=owner))))
def latest(uid,aid,fingerprint,instrument_key):
    raw=cache.get(prefix(uid,aid)+':tick:'+instrument_key)
    if not raw:return {'instrument_key':instrument_key,'data_status':'UNAVAILABLE'}
    row=json.loads(raw);state=status(uid,aid);lease=cache.get(lease_key(uid,aid));lease=lease.decode() if isinstance(lease,bytes) else lease
    live=bool(lease and row.get('_owner')==lease and state.get('owner')==lease and state.get('version')==fingerprint and state.get('market_connected')=='1' and 0<=time.time()-row['received_at']<=10 and 0<=time.time()-row['exchange_timestamp']<=15)
    row.pop('_owner',None);row['data_status']='LIVE' if live else 'STALE';return row

def event_projection(data,expected_client):
    if not isinstance(data,dict) or data.get('Type')!='order_alert' or not isinstance(data.get('Data'),dict):return None
    row=data['Data'];client=row.get('ClientId',row.get('clientId',row.get('dhanClientId')))
    if client is not None and str(client)!=str(expected_client):return None
    def take(*names):return next((row[k] for k in names if k in row),None)
    oid=take('orderNo','OrderNo','orderId')
    if not isinstance(oid,(str,int)):return None
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',str(oid)):return None
    state=take('status','Status','orderStatus')
    if state not in ('TRANSIT','PENDING','PART_TRADED','TRADED','CANCELLED','REJECTED','EXPIRED'):state='UNKNOWN'
    def number(*names):
        v=take(*names)
        return int(v) if isinstance(v,(str,int)) and not isinstance(v,bool) and str(v).isdigit() and len(str(v))<=12 else None
    return dict(order_id=str(oid),status=state,filled_quantity=number('tradedQty','TradedQty','filledQty'),security_id=number('securityId','SecurityId'),received_at=now().isoformat(),source='DHAN_ORDER_UPDATE',fill_authority='REST_RECONCILIATION_REQUIRED')

class PrivateMarketFeed(MarketFeed):
    async def connect(self):
        url=self.market_feed_wss+'?'+urlencode(dict(version=2,token=self.access_token,clientId=self.client_id,authType=2))
        self.ws=await websockets.connect(url,open_timeout=10,close_timeout=3,max_size=65536,max_queue=16,ping_interval=20,logger=_SOCKET_LOG)
        await self.subscribe_instruments()

class PrivateOrderUpdates(OrderUpdate):
    async def open(self):
        ws=await websockets.connect(self.order_feed_wss,open_timeout=10,close_timeout=3,max_size=65536,max_queue=16,ping_interval=20,logger=_SOCKET_LOG)
        await ws.send(json.dumps({'LoginReq':{'MsgCode':42,'ClientId':str(self.client_id),'Token':str(self.access_token)},'UserType':'SELF'}))
        # The reference prints this authentication message. GNK never does.
        return ws

async def run_market(uid,aid,owner,fingerprint,context,instruments):
    feed=PrivateMarketFeed(context,[(SEGMENTS[r['segment']],r['security_id'],21) for r in instruments],version='v2')
    feed.loop.close();feed.loop=asyncio.get_running_loop();asyncio.set_event_loop(feed.loop);backoff=1
    try:
        while True:
            try:
                await feed.connect();connection(uid,aid,owner,fingerprint,'market_connected',True);backoff=1
                while True:
                    raw=await asyncio.wait_for(feed.ws.recv(),timeout=35)
                    if not isinstance(raw,bytes):continue
                    parsed=feed.process_data(raw);value=packet(raw,parsed)
                    if value and not publish(uid,aid,owner,value):return
            except asyncio.CancelledError:raise
            except Exception:pass
            finally:
                connection(uid,aid,owner,fingerprint,'market_connected',False)
                if feed.ws:
                    try:await feed.ws.close()
                    except Exception:pass
            await asyncio.sleep(backoff);backoff=min(60,backoff*2)
    finally:connection(uid,aid,owner,fingerprint,'market_connected',False)

async def run_orders(uid,aid,owner,fingerprint,context):
    feed=PrivateOrderUpdates(context);backoff=1;ws=None
    try:
        while True:
            try:
                ws=await feed.open();connection(uid,aid,owner,fingerprint,'order_connected',True);backoff=1
                async for raw in ws:
                    if len(raw)>65536:raise ValueError()
                    event=event_projection(json.loads(raw),context.get_client_id())
                    if event:
                        if not fenced(uid,aid,owner,"redis.call('SET',ARGV[2],ARGV[3],'EX',86400);return 1",prefix(uid,aid)+':order',json.dumps(event)):return
            except asyncio.CancelledError:raise
            except Exception:pass
            finally:
                connection(uid,aid,owner,fingerprint,'order_connected',False)
                if ws:
                    try:await ws.close()
                    except Exception:pass
            await asyncio.sleep(backoff);backoff=min(60,backoff*2)
    finally:connection(uid,aid,owner,fingerprint,'order_connected',False)

def desired():
    result={}
    with DB() as s:uids=list(s.scalars(select(User.id)))
    for uid in uids:
        with DB() as s:
            set_context(s,uid)
            from .models import ConsentAttempt
            s.execute(delete(ConsentAttempt).where(ConsentAttempt.user_id==uid,ConsentAttempt.expires_at<now()));s.commit()
            user=s.get(User,uid)
            if not user or not user.active or not user.verified:continue
            for a in s.scalars(select(BrokerAccount).where(BrokerAccount.user_id==uid,BrokerAccount.broker=='dhan',BrokerAccount.status=='connected')):
                c=s.scalar(select(BrokerCredential).where(BrokerCredential.user_id==uid,BrokerCredential.account_id==a.id))
                if not c or not c.expires_at or expired(c.expires_at):continue
                raw=cache.get(watch_key(uid,a.id))
                try:watch=json.loads(raw) if raw else None
                except (ValueError,TypeError):watch=None
                if not isinstance(watch,dict):watch=None
                if watch:
                    session=s.get(LoginSession,watch.get('session_id'))
                    if not session or session.user_id!=uid or session.revoked or not session.mfa_complete or expired(session.expires) or time.time()>=watch.get('access_expires',0):watch=None
                pending=s.scalar(select(LiveOrder.id).where(LiveOrder.user_id==uid,LiveOrder.account_id==a.id,LiveOrder.status.notin_(('FILLED','CANCELLED','REJECTED'))).limit(1))
                if not watch and not pending:continue
                try:data=open_credentials(uid,a.id,c.ciphertext);token=data.get('credentials',data)['access_token']
                except Exception:continue
                instruments=watch.get('instruments',[]) if watch else []
                result[(uid,a.id)]={'fingerprint':version(c),'client_id':a.account_identifier,'token':token,'instruments':instruments,'watch_version':json.dumps(instruments,sort_keys=True)}
    return dict(list(result.items())[:32])

async def worker():
    running={}
    async def stop(k):
        tasks,owner,signature=running.pop(k)
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        fenced(*k,owner,"return redis.call('DEL',KEYS[1])")
    try:
        while True:
            cache.set(HEARTBEAT,now().isoformat(),ex=30)
            wanted=await asyncio.to_thread(desired) if settings.dhan_stream_enabled else {}
            for k in list(running):
                current=wanted.get(k);signature=(current['fingerprint'],current['watch_version']) if current else None
                tasks,owner,old=running[k]
                if signature!=old or any(t.done() for t in tasks) or not fenced(*k,owner,"redis.call('EXPIRE',KEYS[1],40);return 1"):await stop(k)
            for k,item in wanted.items():
                if k in running:continue
                owner=uuid.uuid4().hex
                if not cache.set(lease_key(*k),owner,nx=True,ex=40):continue
                context=DhanClient(item['client_id'],item['token']).context
                tasks=[asyncio.create_task(run_orders(*k,owner,item['fingerprint'],context))]
                if item['instruments']:tasks.append(asyncio.create_task(run_market(*k,owner,item['fingerprint'],context,item['instruments'])))
                running[k]=(tasks,owner,(item['fingerprint'],item['watch_version']))
            await asyncio.sleep(2)
    finally:
        for k in list(running):await stop(k)

def main():
    from app import main as application
    from app.database.readiness import check_schema
    from app.database.session import engine
    with engine.connect() as c:check_schema(c)
    while True:
        try:asyncio.run(worker())
        except Exception:print('GNK broker stream service unavailable; retrying without exposing broker credentials.',flush=True)
        time.sleep(5)
if __name__=='__main__':main()
