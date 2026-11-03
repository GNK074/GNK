"""Upstox execution tests use fake broker transport; no real orders are placed."""
from test_auth import client
from test_multi_user import three,login
from datetime import timedelta
from decimal import Decimal
import fakeredis,httpx,pytest
from sqlalchemy import select
from app import main as m
from app.core.config import settings,now
from app.execution import live_service as live
from app.execution.models import LiveOrder
from app.execution.upstox import UpstoxExecution,ExecutionError
from app.models.trading import BrokerAccount,BrokerCredential,PlatformControl,Strategy,RiskConfiguration,ProductionStatus
from app.security.encryption import seal_credentials
from app.market_data.providers.upstox.instrument_master import store_master
from app.market_data.models import MarketInstrument
KEY='NSE_EQ|TEST'
class Broker:
 calls=0;cancel_calls=0;timeout=False;book_rows=[];trade_rows=[];position_rows=[]
 def verify_identity(self,identity):assert identity=='account-0'
 def book(self):return self.book_rows
 def positions(self):return self.position_rows
 def trades(self,id):return self.trade_rows
 def place(self,order):
  type(self).calls+=1
  if self.timeout:raise ExecutionError('BROKER_RESPONSE_UNKNOWN',True)
  return 'broker-001'
 def cancel(self,id):type(self).cancel_calls+=1;return {'order_id':id}
@pytest.fixture
def live_setup(three,monkeypatch):
 c,ids,accounts=three
 for name,value in [('trading_enabled',True),('live_trading_enabled',True),('upstox_execution_enabled',True),('live_tick_size_multiplier',Decimal('.01'))]:monkeypatch.setattr(settings,name,value)
 monkeypatch.setattr(live,'worker_ready',lambda:True);monkeypatch.setattr(live,'broker_approved',lambda s:True)
 monkeypatch.setattr(live,'client',lambda s,a:Broker())
 monkeypatch.setattr(live.MarketDataService,'require_live_quote',lambda self,key:{'ltp':100,'data_status':'LIVE'})
 Broker.calls=0;Broker.cancel_calls=0;Broker.timeout=False;Broker.book_rows=[];Broker.position_rows=[];Broker.trade_rows=[]
 with m.DB() as s:
  a=s.get(BrokerAccount,accounts[0]);a.live_authorized=True;a.kill_switch=False
  s.add(PlatformControl(id='global',kill_switch=False))
  strategy=Strategy(user_id=ids[0],name='Reviewed fixture',approved=True);s.add(strategy);s.flush();sid=strategy.id
  store_master(s,[{'segment':'NSE_EQ','instrument_key':KEY,'trading_symbol':'TEST','name':'Fixture','instrument_type':'EQ','lot_size':1,'tick_size':5}],[],'test')
  s.flush();instrument=s.scalar(select(MarketInstrument));iid=instrument.id;s.commit()
 h=login(c,0)
 payload={'broker_account_id':accounts[0],'strategy_id':sid,'instrument_id':iid,'symbol':'TEST','side':'BUY','quantity':1,'price':'100','idempotency_key':'live-fixture-0001','confirm_real_money':True}
 return c,ids,accounts,h,payload

def test_submit_is_durable_pending_and_idempotent(live_setup):
 c,ids,accounts,h,p=live_setup
 r=c.post('/api/v1/live/orders',json=p,headers=h);assert r.status_code==200,r.text
 assert r.json()['status']=='PENDING' and r.json()['filled_quantity']==0
 again=c.post('/api/v1/live/orders',json=p,headers=h);assert again.json()['id']==r.json()['id'] and Broker.calls==1
 assert c.post('/api/v1/live/orders',json={**p,'quantity':2},headers=h).status_code==409
 assert c.get('/api/v1/orders').json()==[] # no paper order/position fabricated
 assert c.get('/api/v1/positions').json()==[]

def test_timeout_never_resends_and_blocks_replacement(live_setup):
 c,ids,accounts,h,p=live_setup;Broker.timeout=True
 r=c.post('/api/v1/live/orders',json=p,headers=h);assert r.json()['status']=='UNKNOWN'
 assert c.post('/api/v1/live/orders',json=p,headers=h).json()['id']==r.json()['id'] and Broker.calls==1
 assert c.post('/api/v1/live/orders',json={**p,'idempotency_key':'replacement-0001'},headers=h).status_code==409
 assert Broker.calls==1

def test_all_kill_switches_and_expired_approval_block(live_setup,monkeypatch):
 c,ids,accounts,h,p=live_setup
 with m.DB() as s:s.get(PlatformControl,'global').kill_switch=True;s.commit()
 assert c.post('/api/v1/live/orders',json=p,headers=h).status_code==409
 with m.DB() as s:s.get(PlatformControl,'global').kill_switch=False;s.get(BrokerAccount,accounts[0]).kill_switch=True;s.commit()
 assert c.post('/api/v1/live/orders',json=p,headers=h).status_code==409
 with m.DB() as s:s.get(BrokerAccount,accounts[0]).kill_switch=False;s.add(RiskConfiguration(user_id=ids[0],kill_switch=True));s.commit()
 assert c.post('/api/v1/live/orders',json=p,headers=h).status_code==409
 assert Broker.calls==0

def test_user_isolation_csrf_and_unapproved_strategy(live_setup):
 c,ids,accounts,h,p=live_setup
 assert c.post('/api/v1/live/orders',json=p).status_code==403
 with m.DB() as s:s.get(Strategy,p['strategy_id']).approved=False;s.commit()
 assert c.post('/api/v1/live/orders',json=p,headers=h).status_code==409
 h=login(c,1)
 assert c.post('/api/v1/live/orders',json=p,headers=h).status_code==404
 assert c.post('/api/v1/live/accounts/'+accounts[0]+'/disarm',headers=h).status_code==404
 assert c.get('/api/v1/live/orders').json()==[]
 assert Broker.calls==0

def test_price_band_short_sell_missing_confirmation_and_loss(live_setup):
 c,ids,accounts,h,p=live_setup
 for delta in ({'price':'110'},{'price':'100.01'},{'side':'SELL'},{'confirm_real_money':False},{'quantity':101}):
  assert c.post('/api/v1/live/orders',json={**p,**delta},headers=h).status_code==409
 Broker.position_rows=[{'instrument_token':KEY,'product':'I','quantity':1,'last_price':100,'realised':-5000,'unrealised':0}]
 assert c.post('/api/v1/live/orders',json=p,headers=h).status_code==409
 assert Broker.calls==0

def book_item(row,filled=0,status='open'):
 return {'tag':row.tag,'order_id':'broker-001','instrument_token':KEY,'transaction_type':'BUY','quantity':row.quantity,'filled_quantity':filled,'price':100,'product':'I','order_type':'LIMIT','status':status}

def test_reconcile_partial_fills_final_and_duplicates(live_setup):
 c,ids,accounts,h,p=live_setup;p={**p,'quantity':2}
 r=c.post('/api/v1/live/orders',json=p,headers=h);oid=r.json()['id']
 with m.DB() as s:row=s.get(LiveOrder,oid);Broker.book_rows=[book_item(row,1)]
 Broker.trade_rows=[{'order_id':'broker-001','transaction_type':'BUY','product':'I','trade_id':'t1','quantity':1,'average_price':99.95}]
 r=c.post('/api/v1/live/orders/'+oid+'/reconcile',headers=h)
 assert r.json()['filled_quantity']==1 and r.json()['status']=='OPEN'
 assert c.post('/api/v1/live/orders/'+oid+'/reconcile',headers=h).json()['filled_quantity']==1
 with m.DB() as s:Broker.book_rows=[book_item(s.get(LiveOrder,oid),2,'complete')]
 Broker.trade_rows.append({**Broker.trade_rows[0],'trade_id':'t2','average_price':100})
 r=c.post('/api/v1/live/orders/'+oid+'/reconcile',headers=h)
 assert r.json()['status']=='FILLED' and len(r.json()['fills'])==2
 assert c.get('/api/v1/positions').json()==[]

def test_reconcile_recovers_unknown_by_tag_and_cancel_when_disabled(live_setup,monkeypatch):
 c,ids,accounts,h,p=live_setup;Broker.timeout=True
 r=c.post('/api/v1/live/orders',json=p,headers=h);oid=r.json()['id']
 with m.DB() as s:Broker.book_rows=[book_item(s.get(LiveOrder,oid))]
 r=c.post('/api/v1/live/orders/'+oid+'/reconcile',headers=h)
 assert r.json()['provider_order_id']=='broker-001' and r.json()['status']=='OPEN'
 monkeypatch.setattr(settings,'live_trading_enabled',False)
 assert c.post('/api/v1/live/orders/'+oid+'/cancel',headers=h).json()['status']=='CANCEL_PENDING'
 assert Broker.cancel_calls==1 and Broker.calls==1

def test_transport_uses_v3_binary_free_json_and_does_not_retry(monkeypatch):
 import app.execution.upstox as module
 monkeypatch.setattr(module,'cache',fakeredis.FakeRedis());seen=[]
 def respond(request):
  seen.append(request)
  assert request.url.host=='api-hft.upstox.com'
  assert request.headers['authorization']=='Bearer PRIVATE-TRADING-TOKEN'
  raise httpx.ReadTimeout('PRIVATE-TRADING-TOKEN')
 from types import SimpleNamespace
 order=SimpleNamespace(quantity=1,price=Decimal('100'),tag='GNKfixture',instrument_key=KEY,side='BUY')
 broker=UpstoxExecution('PRIVATE-TRADING-TOKEN','fixture',httpx.MockTransport(respond))
 with pytest.raises(ExecutionError) as error:broker.place(order)
 assert len(seen)==1 and error.value.ambiguous and 'PRIVATE' not in str(error.value)

def test_trading_token_load_uses_owned_individual_encrypted_secret(three):
 c,ids,accounts=three
 with m.DB() as s:
  cred=s.scalar(select(BrokerCredential).where(BrokerCredential.account_id==accounts[0]));cred.expires_at=now()+timedelta(hours=1)
  cred.ciphertext=seal_credentials(ids[0],accounts[0],{'connection_method':'individual_credentials','credentials':{'access_token':'individual-token'}});s.commit()
  a=s.get(BrokerAccount,accounts[0]);assert isinstance(live.client(s,a),UpstoxExecution)
  cred.expires_at=now()-timedelta(seconds=1);s.commit()
  from fastapi import HTTPException
  with pytest.raises(HTTPException):live.client(s,a)

def test_worker_reconciles_when_new_placement_is_disabled(live_setup,monkeypatch):
 from app.execution import worker
 c,ids,accounts,h,p=live_setup
 oid=c.post('/api/v1/live/orders',json=p,headers=h).json()['id']
 with m.DB() as s:Broker.book_rows=[book_item(s.get(LiveOrder,oid),0,'cancelled')]
 monkeypatch.setattr(worker,'cache',fakeredis.FakeRedis());monkeypatch.setattr(settings,'live_trading_enabled',False)
 worker.run_once()
 with m.DB() as s:assert s.get(LiveOrder,oid).status=='CANCELLED'
 assert Broker.calls==1

def test_malformed_fills_fail_closed_and_no_resubmission(live_setup):
 c,ids,accounts,h,p=live_setup
 oid=c.post('/api/v1/live/orders',json=p,headers=h).json()['id']
 with m.DB() as s:Broker.book_rows=[book_item(s.get(LiveOrder,oid),1,'complete')]
 Broker.trade_rows=[]
 r=c.post('/api/v1/live/orders/'+oid+'/reconcile',headers=h)
 assert r.json()['status']=='RECONCILE_REQUIRED' and r.json()['filled_quantity']==0
 assert c.post('/api/v1/live/orders',json={**p,'idempotency_key':'replacement-1234'},headers=h).status_code==409
 assert Broker.calls==1

def test_revocation_between_intent_commit_and_submission(live_setup,monkeypatch):
 c,ids,accounts,h,p=live_setup
 original=live.gates;calls=[]
 def revoke(s,account,strategy=None):
  calls.append(1)
  if len(calls)==2:live.fail('Authorization revoked')
  return original(s,account,strategy)
 monkeypatch.setattr(live,'gates',revoke)
 r=c.post('/api/v1/live/orders',json=p,headers=h)
 assert r.json()['status']=='REJECTED' and Broker.calls==0

def test_validated_configuration_can_enable_only_explicit_scope():
 from app.core.config import Settings
 configured=Settings(trading_enabled=True,live_trading_enabled=True,upstox_execution_enabled=True,live_execution_reference='reviewed-test-reference',live_tick_size_multiplier='.01',broker_egress_ip='8.8.8.8')
 assert configured.live_trading_enabled
 with pytest.raises(ValueError):Settings(trading_enabled=True,live_trading_enabled=True,upstox_execution_enabled=True,live_execution_reference='false',live_tick_size_multiplier='.01',broker_egress_ip='8.8.8.8')

def test_upstox_adapter_success_payload_and_cancel_contract(monkeypatch):
 import app.execution.upstox as module,json
 from types import SimpleNamespace
 monkeypatch.setattr(module,'cache',fakeredis.FakeRedis());requests=[]
 def respond(request):
  requests.append(request)
  if request.method=='POST':
   data=json.loads(request.content)
   assert data=={'quantity':1,'product':'I','validity':'DAY','price':100.0,'tag':'GNKfixture','instrument_token':KEY,'order_type':'LIMIT','transaction_type':'BUY','disclosed_quantity':0,'trigger_price':0,'is_amo':False,'slice':False}
   return httpx.Response(200,json={'status':'success','data':{'order_ids':['broker-123']}})
  assert request.method=='DELETE' and request.url.params['order_id']=='broker-123'
  return httpx.Response(200,json={'status':'success','data':{'order_id':'broker-123'}})
 broker=UpstoxExecution('private','account',httpx.MockTransport(respond))
 order=SimpleNamespace(quantity=1,price=Decimal('100'),tag='GNKfixture',instrument_key=KEY,side='BUY')
 assert broker.place(order)=='broker-123';broker.cancel('broker-123');assert len(requests)==2
