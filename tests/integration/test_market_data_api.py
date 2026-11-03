from test_auth import client
from test_multi_user import three,login
import pytest,fakeredis,time
from starlette.websockets import WebSocketDisconnect
from app import main as m
from app.core.config import settings,now,digest
from app.market_data.config import market_settings as cfg
from app.market_data.models import MarketEntitlement,MarketSubscription,MarketInstrument,MarketProviderStatus
from app.market_data.redis_store import RedisStore
from app.market_data.providers.upstox.instrument_master import store_master
from app.market_data import router,service,websocket_manager
KEY='NSE_EQ|INE123456789'
@pytest.fixture
def market(three,monkeypatch):
 c,ids,_=three;store=RedisStore(fakeredis.FakeRedis())
 for module in (router,service,websocket_manager):monkeypatch.setattr(module,'get_store',lambda:store)
 monkeypatch.setattr(cfg,'marketdata_distribution_approved',True);monkeypatch.setattr(cfg,'marketdata_approval_reference','OFFLINE-TEST-ONLY');monkeypatch.setattr(cfg,'upstox_enabled',True)
 monkeypatch.setattr(settings,'enable_mfa',False)
 with m.DB() as s:
  store_master(s,[{'segment':'NSE_EQ','instrument_key':KEY,'trading_symbol':'TEST','name':'Offline fixture','instrument_type':'EQ','lot_size':1,'tick_size':5}],[],'fixture')
  s.add(MarketProviderStatus(provider='upstox',enabled=True))
  for uid in ids:s.add(MarketEntitlement(user_id=uid,enabled=True,segments=['NSE_EQ'],modes=['ltpc'],max_instruments=1))
  s.commit()
 return c,ids,store

def test_owned_subscriptions_permissions_and_no_token_leak(market,monkeypatch):
 c,ids,store=market;h=login(c,0)
 r=c.post('/api/v1/marketdata/subscriptions',headers=h,json={'instrument_keys':[KEY],'mode':'ltpc'});assert r.status_code==200,r.text
 sid=r.json()[0]['id']
 assert c.get('/api/v1/marketdata/instruments/search?q=TEST').json()['items'][0]['instrument_key']==KEY
 assert c.get('/api/v1/marketdata/quotes',params={'instrument_keys':KEY,'mode':'full'}).status_code==403
 assert c.post('/api/v1/marketdata/subscriptions',json={'instrument_keys':[KEY]}).status_code==403
 h=login(c,1);assert c.get('/api/v1/marketdata/subscriptions').json()==[]
 assert c.delete('/api/v1/marketdata/subscriptions/'+sid,headers=h).status_code==404
 assert c.post('/api/v1/admin/marketdata/provider/enable',headers=h).status_code==403
 monkeypatch.setattr(cfg,'marketdata_distribution_approved',False)
 assert c.get('/api/v1/marketdata/quotes',params={'instrument_keys':KEY}).status_code==403
 assert c.get('/api/v1/marketdata/status').json()['distribution_approved'] is False

def test_missing_quotes_no_fabricated_prices_and_invalid_history(market,monkeypatch):
 c,ids,store=market;login(c,0)
 with m.DB() as s:s.get(MarketProviderStatus,'upstox').enabled=False;s.commit()
 r=c.get('/api/v1/marketdata/quotes',params={'instrument_keys':KEY});assert r.status_code==200,r.text
 assert r.json()['items'][0]['ltp'] is None and r.json()['items'][0]['data_status']=='MISSING'
 instrument=c.get('/api/v1/marketdata/instruments').json()['items'][0]
 r=c.get('/api/v1/marketdata/history',params={'instrument_id':instrument['id'],'interval':'99x'});assert r.status_code==422
 r=c.get('/api/v1/marketdata/history',params={'instrument_id':instrument['id'],'interval':'1m'});assert r.status_code==200 and r.json()['items']==[]

def test_socket_invalid_origin_missing_ticket_and_replay(market,monkeypatch):
 c,ids,store=market;h=login(c,0)
 with pytest.raises(WebSocketDisconnect):
  with c.websocket_connect('/ws/v1/marketdata',headers={'origin':'https://evil.example'}):pass
 proof={'user_id':ids[0],'session_id':'fixture','access_expires':time.time()+60}
 monkeypatch.setattr(websocket_manager,'socket_identity',lambda p:ids[0])
 store.ticket(digest('one-time-proof'),proof)
 origin=settings.origins[0]
 with c.websocket_connect('/ws/v1/marketdata',subprotocols=['gnk.marketdata','one-time-proof'],headers={'origin':origin}) as ws:
  ws.send_json({'action':'PING'});assert ws.receive_json()['type']=='PONG'
  ws.send_json({'action':'SUBSCRIBE','instrument_keys':[KEY],'mode':'full'})
  while True:
   response=ws.receive_json()
   if response['type']=='error':break
  assert 'not permitted' in response['message']
  ws.close()
  with pytest.raises(WebSocketDisconnect):
   while True:ws.receive_json()
 with pytest.raises(WebSocketDisconnect):
  with c.websocket_connect('/ws/v1/marketdata',subprotocols=['gnk.marketdata','one-time-proof'],headers={'origin':origin}):pass

def test_expired_or_revoked_session_cannot_use_ticket(market):
 from fastapi import HTTPException
 c,ids,store=market
 with pytest.raises(HTTPException):websocket_manager.socket_identity({'user_id':ids[0],'session_id':'missing','access_expires':time.time()+60})
 with pytest.raises(HTTPException):websocket_manager.socket_identity({'user_id':ids[0],'session_id':'missing','access_expires':time.time()-1})
