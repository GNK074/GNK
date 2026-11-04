"""GNK workflows use fake broker HTTP/socket transports; never real orders."""
from test_auth import client
from test_multi_user import three,login
from test_portfolio import portfolio
from test_live_execution import live_setup,Broker
from app import main as m
from app.core.config import settings,now
from app.brokers.dhan import instruments,streams,stream_routes,authentication as consent
from app.brokers.dhan.client import DhanClient,DhanError
from app.brokers.dhan.execution import DhanExecution
from app.execution import live_service as live
from app.execution.upstox import ExecutionError
from app.execution.models import LiveOrder
from app.models.trading import BrokerAccount,BrokerCredential
from app.models.identity import User,LoginSession
from app.brokers.dhan.models import ConsentAttempt
from app.market_data.models import MarketInstrument
from app.security.encryption import seal_credentials,open_credentials
from app.portfolio.service import version
from sqlalchemy import select
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from types import SimpleNamespace
import pytest,httpx,fakeredis,json,struct,time,asyncio

MASTER='SEM_EXM_EXCH_ID,SEM_SEGMENT,SEM_SMST_SECURITY_ID,SEM_INSTRUMENT_NAME,SEM_TRADING_SYMBOL,SEM_LOT_UNITS,SEM_TICK_SIZE\nNSE,E,1330,EQUITY,TEST,1,5\nBSE,E,500325,EQUITY,TESTB,1,5\nNSE,D,99,OPTIDX,OPTION,25,5\n'

def test_instrument_import_namespace_stable_ids_and_reject_invalid():
 rows=instruments.parse(MASTER.splitlines());assert len(rows)==2 and rows[0]['instrument_key']=='DHAN|NSE_EQ|1330'
 assert rows[0]['tick_size']==5
 with pytest.raises(DhanError):instruments.parse(['unexpected,header'])
 with pytest.raises(DhanError):instruments.parse((MASTER+'NSE,E,1330,EQUITY,TEST,1,5\n').splitlines())
 with pytest.raises(DhanError):instruments.download(httpx.MockTransport(lambda r:httpx.Response(302,headers={'location':'https://example.com'})))

def test_execution_capability_and_ambiguous_no_retry(monkeypatch):
 calls=[]
 def handler(r):
  calls.append(r)
  if r.url.path=='/v2/profile':return httpx.Response(200,json={'dhanClientId':'123'})
  if r.url.path=='/v2/ip/getIP':return httpx.Response(200,json={'primaryIP':'130.210.34.12'})
  if r.method=='POST':return httpx.Response(200,json={'orderId':'order-1'})
  if r.method=='DELETE':return httpx.Response(200,json={'orderId':'order-1'})
  return httpx.Response(200,json=[])
 monkeypatch.setattr(settings,'broker_egress_ip','130.210.34.12')
 adapter=DhanExecution('123','fixture-only','a','u',httpx.MockTransport(handler))
 adapter.verify_identity('123')
 row=SimpleNamespace(instrument_key='DHAN|NSE_EQ|1330',side='BUY',quantity=1,price=Decimal('100'),tag='GNKfixture')
 assert adapter.place(row)=='order-1';adapter.cancel('order-1')
 payload=json.loads(calls[2].content)
 assert payload['securityId']=='1330' and payload['correlationId']=='GNKfixture' and payload['productType']=='INTRADAY'
 readonly=DhanClient('123','fixture',httpx.MockTransport(handler))
 with pytest.raises(DhanError):readonly.sdk.place_order('1330','NSE_EQ','BUY',1,'LIMIT','INTRADAY',100)
 with pytest.raises(DhanError):adapter.client.sdk.modify_order('order-1','LIMIT','',1,100,0,0,'DAY')
 calls.clear()
 adapter=DhanExecution('123','fixture','a','u',httpx.MockTransport(lambda r:(calls.append(r) or httpx.Response(500,json={'secret':'never'}))))
 with pytest.raises(ExecutionError) as e:adapter.place(row)
 assert e.value.ambiguous and len(calls)==1 and 'never' not in str(e.value)

@pytest.fixture
def dhan_live(live_setup,monkeypatch):
 c,ids,aids,h,p=live_setup
 monkeypatch.setattr(settings,'dhan_execution_enabled',True);monkeypatch.setattr(settings,'dhan_tick_size_multiplier',Decimal('.01'))
 monkeypatch.setattr(live,'broker_approved',lambda s,broker='upstox':True)
 monkeypatch.setattr(live,'quote_for',lambda *a:{'ltp':'100','data_status':'LIVE'})
 clock=datetime.now(timezone.utc).replace(hour=5,minute=0,second=0,microsecond=0)
 while clock.weekday()>4:clock-=timedelta(days=1)
 monkeypatch.setattr(live,'now',lambda:clock)
 with m.DB() as s:
  s.get(BrokerAccount,aids[0]).broker='dhan';i=s.get(MarketInstrument,p['instrument_id']);i.provider='dhan';i.instrument_key='DHAN|NSE_EQ|1330';i.synced_at=clock;s.commit()
 return c,ids,aids,h,p

def test_dhan_durable_intent_idempotency_and_unknown_block(dhan_live):
 c,ids,aids,h,p=dhan_live;Broker.timeout=True
 r=c.post('/api/v1/live/orders',headers=h,json=p);assert r.status_code==200,r.text
 assert r.json()['status']=='UNKNOWN'
 assert c.post('/api/v1/live/orders',headers=h,json=p).json()['id']==r.json()['id'] and Broker.calls==1
 assert c.post('/api/v1/live/orders',headers=h,json={**p,'idempotency_key':'new-intent-1234'}).status_code==409
 with m.DB() as s:assert len(s.get(LiveOrder,r.json()['id']).tag)<=30

def test_dhan_scope_provider_and_activation_isolation(dhan_live,monkeypatch):
 c,ids,aids,h,p=dhan_live
 monkeypatch.setattr(settings,'dhan_execution_enabled',False)
 assert c.post('/api/v1/live/orders',headers=h,json=p).status_code==409
 assert settings.upstox_execution_enabled is True
 monkeypatch.setattr(settings,'dhan_execution_enabled',True)
 with m.DB() as s:s.get(MarketInstrument,p['instrument_id']).provider='upstox';s.commit()
 assert c.post('/api/v1/live/orders',headers=h,json=p).status_code==409 and Broker.calls==0
 assert c.post('/api/v1/live/accounts/'+aids[0]+'/arm',headers=h,json={'confirmation':'ENABLE LIVE UPSTOX'}).status_code==422

def test_binary_parser_and_stale_fenced_ticks(monkeypatch):
 cache=fakeredis.FakeRedis();monkeypatch.setattr(streams,'cache',cache)
 raw=struct.pack('<BHBIfI',2,16,1,1330,100.25,int(time.time()))
 from dhanhq import DhanContext
 feed=streams.PrivateMarketFeed(DhanContext('123','fixture'),[],version='v2')
 parsed=feed.process_data(raw);feed.loop.close()
 value=streams.packet(raw,parsed);assert value['instrument_key']=='DHAN|NSE_EQ|1330' and value['ltp']=='100.25'
 cache.set(streams.lease_key('u','a'),'owner',ex=40)
 streams.connection('u','a','owner','version','market_connected',True)
 assert streams.publish('u','a','other',value)==0
 assert streams.publish('u','a','owner',value)==1
 assert streams.latest('u','a','version',value['instrument_key'])['data_status']=='LIVE'
 assert streams.latest('u','a','new-version',value['instrument_key'])['data_status']=='STALE'
 assert streams.latest('other','a','version',value['instrument_key'])['data_status']=='UNAVAILABLE'
 value['exchange_timestamp']-=60;streams.publish('u','a','owner',value)
 assert streams.latest('u','a','version',value['instrument_key'])['data_status']=='STALE'
 assert streams.packet(b'bad',{}) is None

def test_order_projection_never_returns_raw_auth_or_nested_data():
 event={'Type':'order_alert','Data':{'ClientId':'123','orderNo':'o1','status':'TRADED','tradedQty':1,'securityId':'1330','Token':'private-fixture'}}
 result=streams.event_projection(event,'123');assert result['filled_quantity']==1 and 'private-fixture' not in json.dumps(result)
 assert result['fill_authority']=='REST_RECONCILIATION_REQUIRED'
 assert streams.event_projection(event,'other') is None
 event['Data']['tradedQty']={'Token':'private-fixture'}
 assert streams.event_projection(event,'123')['filled_quantity'] is None

@pytest.fixture
def private(portfolio,monkeypatch):
 c,ids,aids=portfolio;cache=fakeredis.FakeRedis()
 monkeypatch.setattr(streams,'cache',cache);monkeypatch.setattr(stream_routes,'cache',cache)
 with m.DB() as s:
  for aid in aids:s.get(BrokerAccount,aid).broker='dhan'
  rows=instruments.parse(MASTER.splitlines());instruments.store(s,rows);s.commit()
  iid=s.scalar(select(MarketInstrument.id).where(MarketInstrument.segment=='NSE_EQ'))
 return c,ids,aids,iid,cache

def test_private_subscription_owner_csrf_ticket_replay_and_revocation(private):
 c,ids,aids,iid,cache=private;h=login(c,0)
 body={'account_id':aids[0],'instrument_ids':[iid]}
 assert c.post('/api/v1/dhan/stream/subscribe',json=body).status_code==403
 assert c.post('/api/v1/dhan/stream/subscribe',headers=h,json={**body,'account_id':aids[1]}).status_code==404
 assert c.post('/api/v1/dhan/stream/subscribe',headers=h,json=body).json()['subscribed']==1
 response=c.post('/api/v1/dhan/stream-ticket',headers=h,json={'account_id':aids[0]});assert response.status_code==200,response.text
 ticket=response.json()['ticket']
 origin=settings.origins[0]
 with c.websocket_connect('/ws/v1/dhan',subprotocols=['gnk.dhan',ticket],headers={'origin':origin}) as ws:
  data=ws.receive_json();assert data['ticks'][0]['data_status']=='UNAVAILABLE' and 'version' not in data['connection']
  with m.DB() as s:
   session=s.scalar(select(LoginSession).where(LoginSession.user_id==ids[0],LoginSession.revoked.is_(False)));session.revoked=True;s.commit()
  from starlette.websockets import WebSocketDisconnect
  with pytest.raises(WebSocketDisconnect):ws.receive_json()
 from starlette.websockets import WebSocketDisconnect
 with pytest.raises(WebSocketDisconnect):
  with c.websocket_connect('/ws/v1/dhan',subprotocols=['gnk.dhan',ticket],headers={'origin':origin}):pass

def test_consent_encrypted_one_time_session_bound(private,monkeypatch):
 c,ids,aids,iid,cache=private;h=login(c,0)
 monkeypatch.setattr(settings,'dhan_oauth_enabled',True);monkeypatch.setattr(consent,'limit',lambda *a:None)
 monkeypatch.setattr(consent.ConsentProvider,'start',lambda self,*a,**k:'https://auth.dhan.co/login/consentApp-login?consentAppId=fixture')
 calls=[]
 def consume(self,*a,**k):calls.append(1);return {'dhanClientId':'account-0','accessToken':'broker-token-fixture'}
 monkeypatch.setattr(consent.ConsentProvider,'consume',consume)
 from app.brokers.individual import routes as individual
 def connect(broker,data,request,user,s):
  assert broker=='dhan' and data.credentials['access_token'].get_secret_value()=='broker-token-fixture'
 monkeypatch.setattr(individual,'connect_individual',connect)
 body={'client_id':'account-0','app_id':'app-fixture','app_secret':'secret-fixture','owns_account':True,'terms_accepted':True}
 assert c.post('/api/v1/dhan/oauth/start',json=body).status_code==403
 r=c.post('/api/v1/dhan/oauth/start',json=body,headers=h);assert r.status_code==200,r.text
 assert 'secret-fixture' not in r.text and 'HttpOnly' in r.headers['set-cookie']
 cookie=c.cookies.get(consent.COOKIE)
 with m.DB() as s:
  attempt=s.scalar(select(ConsentAttempt));assert 'secret-fixture' not in attempt.secret_ciphertext
  assert open_credentials(ids[0],aids[0],attempt.secret_ciphertext)['app_secret']=='secret-fixture'
 callback=c.get('/api/v1/dhan/oauth/callback?tokenId=broker-one-time-code',follow_redirects=False)
 assert callback.status_code==303 and callback.headers['location'].endswith('/user/dhan?oauth=connected') and 'broker-token' not in callback.text
 with m.DB() as s:
  attempt=s.scalar(select(ConsentAttempt));assert attempt.consumed and attempt.secret_ciphertext==''
 c.cookies.set(consent.COOKIE,cookie)
 assert c.get('/api/v1/dhan/oauth/callback?tokenId=replay',follow_redirects=False).headers['location'].endswith('failed')
 assert len(calls)==1

def test_sdk_execution_normalizes_book_positions_and_per_order_fills(monkeypatch):
 def handler(r):
  if r.url.path=='/v2/orders':return httpx.Response(200,json=[{'orderId':'o1','correlationId':'GNK1','exchangeSegment':'NSE_EQ','securityId':'1330','transactionType':'BUY','quantity':2,'filledQty':1,'price':100,'productType':'INTRADAY','orderType':'LIMIT','orderStatus':'PART_TRADED'}])
  if r.url.path=='/v2/positions':return httpx.Response(200,json=[{'exchangeSegment':'NSE_EQ','securityId':'1330','netQty':1,'costPrice':100,'realizedProfit':0,'unrealizedProfit':1,'productType':'INTRADAY'}])
  assert r.url.path=='/v2/trades/o1'
  return httpx.Response(200,json=[{'orderId':'o1','exchangeTradeId':'t1','transactionType':'BUY','productType':'INTRADAY','tradedQuantity':1,'tradedPrice':'99.95'}])
 adapter=DhanExecution('123','fixture','a','u',httpx.MockTransport(handler),credential_version='v')
 assert adapter.book()[0]['status']=='open' and adapter.book()[0]['instrument_token']=='DHAN|NSE_EQ|1330'
 monkeypatch.setattr(streams,'latest',lambda *a:{'data_status':'STALE','ltp':101})
 with pytest.raises(ExecutionError,match='POSITION_EXPOSURE_PRICE_UNAVAILABLE'):adapter.positions()
 monkeypatch.setattr(streams,'latest',lambda *a:{'data_status':'LIVE','ltp':101})
 assert adapter.positions()[0]['last_price']==101
 assert adapter.trades('o1')[0]['average_price']==Decimal('99.95')

def test_private_ticket_origin_guard_and_account_disconnect(private):
 c,ids,aids,iid,cache=private;h=login(c,0)
 ticket=c.post('/api/v1/dhan/stream-ticket',headers=h,json={'account_id':aids[0]}).json()['ticket']
 from starlette.websockets import WebSocketDisconnect
 with pytest.raises(WebSocketDisconnect):
  with c.websocket_connect('/ws/v1/dhan',subprotocols=['gnk.dhan',ticket],headers={'origin':'https://untrusted.example'}):pass
 with m.DB() as s:s.get(BrokerAccount,aids[0]).status='disconnected';s.commit()
 with pytest.raises(WebSocketDisconnect):
  with c.websocket_connect('/ws/v1/dhan',subprotocols=['gnk.dhan',ticket],headers={'origin':settings.origins[0]}):pass

def test_invalid_consent_cookie_cannot_exchange_token(private,monkeypatch):
 c,ids,aids,iid,cache=private;login(c,0);monkeypatch.setattr(settings,'dhan_oauth_enabled',True)
 def forbidden(*a,**k):raise AssertionError('Token exchange must not run')
 monkeypatch.setattr(consent.ConsentProvider,'consume',forbidden)
 response=c.get('/api/v1/dhan/oauth/callback?tokenId=fixture',follow_redirects=False)
 assert response.headers['location'].endswith('failed') and response.headers['Cache-Control']=='no-store'

def test_order_socket_authentication_is_never_printed(monkeypatch,capsys):
 from dhanhq import DhanContext
 class Socket:
  sent=[]
  async def send(self,message):self.sent.append(json.loads(message))
 socket=Socket()
 async def connect(*a,**k):assert k['max_size']==65536;return socket
 monkeypatch.setattr(streams.websockets,'connect',connect)
 assert asyncio.run(streams.PrivateOrderUpdates(DhanContext('123','secret-fixture')).open()) is socket
 assert socket.sent[0]['LoginReq']['Token']=='secret-fixture'
 assert 'secret-fixture' not in capsys.readouterr().out

def test_master_sync_is_superadmin_only_and_preserves_instrument_ids(private,monkeypatch):
 c,ids,aids,iid,cache=private;h=login(c,0)
 assert c.post('/api/v1/dhan/instruments/sync',headers=h).status_code==403
 with m.DB() as s:s.get(User,ids[0]).role='SUPER_ADMIN';s.commit()
 monkeypatch.setattr(instruments,'download',lambda:instruments.parse(MASTER.splitlines()))
 result=c.post('/api/v1/dhan/instruments/sync',headers=h);assert result.status_code==200,result.text
 assert result.json()['imported']==2
 assert c.get('/api/v1/dhan/instruments',params={'q':'TEST'}).json()['items'][0]['id']==iid

def test_private_worker_ignores_bad_credentials_and_expired_sessions(private,monkeypatch):
 c,ids,aids,iid,cache=private;h=login(c,0)
 c.post('/api/v1/dhan/stream/subscribe',headers=h,json={'account_id':aids[0],'instrument_ids':[iid]})
 with m.DB() as s:
  cr=s.scalar(select(BrokerCredential).where(BrokerCredential.account_id==aids[0]));cr.ciphertext='corrupt-fixture';s.commit()
 assert streams.desired()=={}
 with m.DB() as s:
  cr=s.scalar(select(BrokerCredential).where(BrokerCredential.account_id==aids[0]));cr.ciphertext=seal_credentials(ids[0],aids[0],{'credentials':{'access_token':'fixture'}});s.commit()
 assert (ids[0],aids[0]) in streams.desired()
 with m.DB() as s:
  session=s.scalar(select(LoginSession).where(LoginSession.user_id==ids[0]));session.revoked=True;s.commit()
 assert streams.desired()=={}
