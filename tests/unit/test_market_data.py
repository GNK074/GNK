"""Offline contract tests: official protobuf, Redis fencing, calendars and imports."""
import asyncio,json
from datetime import timedelta,date
from types import SimpleNamespace
import fakeredis,httpx,pytest
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
from app.core.config import now
from app.database.session import Base
from app.models import identity
from app.market_data.config import MarketSettings,market_settings as cfg
from app.market_data.models import MarketInstrument,MarketCandle
from app.market_data.redis_store import RedisStore,LEASE
from app.market_data.normalizer import normalize_tick,normalize_quote,InvalidMarketData
from app.market_data.market_calendar import quality
from app.market_data.providers.base import ProviderError
from app.market_data.providers.upstox.protobuf_decoder import decode
from app.market_data.providers.upstox import MarketDataFeed_pb2 as pb
from app.market_data.providers.upstox.instrument_master import parse_instrument,store_master,download
from app.market_data.providers.upstox.historical import parse_candle,store_candles,windows,historical
from app.market_data.providers.upstox.client import UpstoxClient
from app.market_data.provider_manager import FeedManager

KEY='NSE_EQ|INE123456789'
def tick(offset=0,price=120):
 stamp=(now()+timedelta(seconds=offset)).isoformat()
 return normalize_tick(KEY,{'ltpc':{'ltp':price,'ltt':stamp,'cp':115}},stamp)
@pytest.fixture
def store():return RedisStore(fakeredis.FakeRedis())
@pytest.fixture
def db():
 engine=create_engine('sqlite://');Base.metadata.create_all(engine)
 with Session(engine) as s:yield s
 engine.dispose()
def master(key=KEY):return {'segment':'NSE_EQ','instrument_key':key,'trading_symbol':'GNK','name':'Test instrument','instrument_type':'EQ','lot_size':1,'tick_size':5}
def test_disabled_defaults_and_approval_reference():
 settings=MarketSettings(_env_file=None)
 assert not settings.upstox_enabled and not settings.marketdata_distribution_approved
 with pytest.raises(ValueError):MarketSettings(marketdata_distribution_approved=True)
 with pytest.raises(ValueError):MarketSettings(marketdata_allowed_segments='UNKNOWN')
 with pytest.raises(ValueError):MarketSettings(marketdata_special_sessions='[]')
def test_official_binary_protobuf_and_missing_fields():
 frame=pb.FeedResponse(currentTs=int(now().timestamp()*1000))
 frame.feeds[KEY].ltpc.ltp=120;frame.feeds[KEY].ltpc.ltt=int(now().timestamp()*1000)
 msg=decode(frame.SerializeToString());value=normalize_tick(KEY,msg['feeds'][KEY],msg['currentTs'])
 assert value['ltp']==120 and value['oi'] is None and value['bid']==[]
 for bad in (b'\xff','not binary',b''):
  with pytest.raises(ProviderError):decode(bad)
def test_normalizer_rejects_nonfinite_and_future():
 with pytest.raises(InvalidMarketData):tick(price=float('nan'))
 with pytest.raises(InvalidMarketData):tick(offset=30)
def test_quality_never_labels_rest_stale_or_disconnected_live():
 assert quality(tick(),True,{'status':'NORMAL_OPEN'})['data_status']=='LIVE'
 assert quality(tick(-60),True,{'status':'NORMAL_OPEN'})['data_status']=='STALE'
 assert quality(tick(),False,{'status':'NORMAL_OPEN'})['data_status']=='DISCONNECTED'
 assert quality(tick(),True,{'status':'NORMAL_CLOSE'})['data_status']=='MARKET_CLOSED'
 assert quality(tick(),True)['data_status']=='UNVERIFIED_SESSION'
 raw={'last_price':120,'last_trade_time':int(now().timestamp()*1000),'timestamp':now().isoformat()}
 assert quality(normalize_quote(KEY,raw),True,{'status':'NORMAL_OPEN'})['data_status']=='SNAPSHOT'
def test_singleton_fencing_ordering_duplicates_and_expiry(store):
 assert store.acquire('a') and not store.acquire('b')
 value=tick();assert store.put_tick(value,'a')==1
 assert store.put_tick(value,'a')==0
 assert store.put_tick(tick(-10),'a')==-1
 older=tick(-10);older['provider_timestamp']=now().isoformat()
 assert store.put_tick(older,'a')==-1
 assert store.put_tick(tick(),'b')==-3
 assert store.renew('a') and not store.renew('b')
 assert store.latest(KEY)['ltp']==120 and '_fingerprint' not in store.latest(KEY)
 assert store.client.ttl(store.tick_key(KEY))>0
 assert store.release('b')==0 and store.release('a')==1 and store.acquire('b')
 assert store.put_tick(tick(),'a')==-3
 assert store.set_state('a',{'state':'CONNECTED'})==0
def test_tickets_one_use_slots_and_rate_limits(store):
 store.ticket('hash',{'user_id':'x'});assert store.consume_ticket('hash')=={'user_id':'x'};assert store.consume_ticket('hash') is None
 assert all(store.socket_slot('u',str(i)) for i in range(3));assert not store.socket_slot('u','fourth')
 store.socket_slot('u','0',True);assert store.socket_slot('u','fourth')
 assert store.user_allowed('u',1) and not store.user_allowed('u',1)
 assert store.user_allowed('other',1)
def test_instrument_upsert_preserves_identity_and_history(db):
 assert store_master(db,[master()],[],'v1')==1;db.commit()
 item=db.scalar(select(MarketInstrument));original=item.id
 assert store_master(db,[master()],[],'v2')==1;db.commit();db.expire_all()
 assert db.scalar(select(MarketInstrument)).id==original
 store_master(db,[master('NSE_EQ|OTHER')],[],'v3');db.commit();db.expire_all()
 assert db.get(MarketInstrument,original).status=='UNLISTED'
 assert parse_instrument({**master(),'segment':'MCX_FO'},'v') is None
 with pytest.raises(InvalidMarketData):parse_instrument({**master(),'lot_size':1.5},'v')
def test_candle_upsert_utc_and_no_interpolation(db):
 store_master(db,[master()],[],'v1');db.commit();item=db.scalar(select(MarketInstrument))
 rows=[['2025-10-01T09:15:00+05:30',100,110,90,105,10,2],['2025-10-01T09:17:00+05:30',105,115,100,110,20,3]]
 assert parse_candle(rows[0],item,'1m')['timestamp'].hour==3
 store_candles(db,rows+rows,item,'1m');db.commit();store_candles(db,rows,item,'1m');db.commit()
 assert db.scalar(select(func.count()).select_from(MarketCandle))==2
 with pytest.raises(InvalidMarketData):parse_candle(['2025-10-01T09:15:00',100,90,110,105,10],item,'1m')
 chunks=list(windows(date(2025,1,1),date(2025,4,1),'1m'));assert len(chunks)==4
 assert all((b-a).days<28 for a,b in chunks)
def test_historical_request_encodes_original_key():
 calls=[]
 class Client:
  async def get(self,path):calls.append(path);return {'candles':[]}
 asyncio.run(historical(Client(),'NSE_INDEX|Nifty 50','1h',date(2025,1,1),date(2025,1,2)))
 assert 'NSE_INDEX%7CNifty%2050/hours/1/2025-01-02/2025-01-01' in calls[0]
def test_auth_errors_redacted_and_readonly_endpoints(store):
 def respond(request):assert request.headers['authorization']=='Bearer PRIVATE';return httpx.Response(401,json={'error':'PRIVATE'})
 client=UpstoxClient('PRIVATE',store,httpx.MockTransport(respond))
 with pytest.raises(ProviderError) as error:asyncio.run(client.get('/v2/market-quote/quotes'))
 assert str(error.value)=='PROVIDER_AUTHORIZATION_FAILED' and 'PRIVATE' not in str(error.value)
 with pytest.raises(ProviderError):asyncio.run(client.get('/v2/order/place'))
def test_empty_or_redirected_master_rejected():
 import gzip
 transport=httpx.MockTransport(lambda r:httpx.Response(200,content=gzip.compress(b'[]')))
 with pytest.raises(ProviderError):asyncio.run(download('complete.json.gz',transport))
 assert asyncio.run(download('suspended-instrument.json.gz',transport))[0]==[]
def test_restore_subscriptions_after_reconnect_and_drop_obsolete(store):
 class Provider:
  def __init__(self):self.calls=[]
  async def subscribe(self,keys,mode):self.calls.append(('sub',keys,mode))
  async def unsubscribe(self,keys):self.calls.append(('unsub',keys))
 p=Provider();desired={KEY:'full'};manager=FeedManager(p,store,'owner',lambda:dict(desired),lambda:True)
 asyncio.run(manager.restore());manager.active={};asyncio.run(manager.restore())
 assert len(p.calls)==2 and p.calls[0]==p.calls[1]
 desired.clear();asyncio.run(manager.restore());assert p.calls[-1]==('unsub',[KEY])


def test_stream_reconnect_restores_subscription_and_cancels_cleanly(store):
 async def scenario():
  store.acquire('leader');second=asyncio.Event()
  class Socket:
   def __init__(self,number):self.number=number
   async def recv(self):
    if self.number==1:raise ConnectionError('offline fixture')
    await asyncio.Event().wait()
  class Provider:
   def __init__(self):self.count=0;self.calls=[];self.socket=None
   async def connect(self):
    self.count+=1;self.socket=Socket(self.count)
   async def subscribe(self,keys,mode):
    self.calls.append((keys,mode))
    if self.count==2:second.set()
   async def unsubscribe(self,keys):pass
   async def disconnect(self):pass
  p=Provider();manager=FeedManager(p,store,'leader',lambda:{KEY:'ltpc'},lambda:True)
  task=asyncio.create_task(manager.run())
  try:await asyncio.wait_for(second.wait(),6)
  finally:
   task.cancel();await asyncio.gather(task,return_exceptions=True)
  assert p.count==2 and p.calls[:2]==[([KEY],'ltpc'),([KEY],'ltpc')]
  assert manager.attempt==1
 asyncio.run(scenario())
