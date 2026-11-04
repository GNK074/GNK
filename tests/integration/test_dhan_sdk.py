from test_auth import client
from test_multi_user import three,login
from test_portfolio import portfolio
from app import main as m
from app.core.config import now
from app.brokers.dhan.client import DhanClient,DhanError,SDK_VERSION
from app.brokers.dhan import routes
from app.brokers.dhan.analytics import candles,aggregate,indicators
from app.models.trading import BrokerAccount,BrokerCredential
from app.portfolio.models import PortfolioSnapshot
from sqlalchemy import select,func
from datetime import timedelta,datetime,timezone
from decimal import Decimal
from importlib.metadata import version
import httpx,pytest,json


def test_pinned_sdk_business_methods_and_guarded_transport():
 assert version('dhanhq')==SDK_VERSION
 calls=[]
 def handler(req):
  calls.append(req)
  if req.url.path=='/v2/fundlimit':return httpx.Response(200,json={'availabelBalance':'100.25'})
  if req.url.path=='/v2/marketfeed/ltp':
   body=json.loads(req.content);assert 'dhanClientId' not in body
   return httpx.Response(200,json={'status':'success','data':{'NSE_EQ':{'1330':{'last_price':100.25}}}})
  return httpx.Response(200,json=[])
 c=DhanClient('TEST','fake-only',httpx.MockTransport(handler))
 assert c.read('holdings')==[] and c.read('funds')['availabelBalance']=='100.25'
 assert c.quote({'NSE_EQ':[1330]})['NSE_EQ']['1330']['last_price']==Decimal('100.25')
 assert all(r.headers['client-id']=='TEST' and r.headers['access-token']=='fake-only' for r in calls)
 with pytest.raises(DhanError,match='DHAN_OPERATION_NOT_ENABLED'):
  c.sdk.place_order('1330','NSE_EQ','BUY',1,'LIMIT','INTRADAY',100)
 with pytest.raises(DhanError,match='DHAN_OPERATION_NOT_ENABLED'):c.sdk.cancel_order('123')
 assert len(calls)==3

@pytest.mark.parametrize('code,error',[(401,'SESSION_EXPIRED'),(403,'PERMISSION_DENIED'),(429,'RATE_LIMITED'),(500,'DHAN_UNAVAILABLE'),(302,'DHAN_REQUEST_REJECTED')])
def test_sdk_failures_are_sanitized_and_not_retried(code,error,caplog):
 calls=[]
 def handler(req):calls.append(req);return httpx.Response(code,json={'accessToken':'sensitive-fixture','errorMessage':'do-not-echo'})
 c=DhanClient('T','private-fixture',httpx.MockTransport(handler))
 with pytest.raises(DhanError,match=error) as e:c.read('holdings')
 assert len(calls)==1 and 'private' not in str(e.value) and 'sensitive' not in caplog.text

class FixtureClient:
 calls=0
 def __init__(self,*args):pass
 def profile(self):return {'dhanClientId':'CLIENT123456','tokenValidity':'01/01/2027 10:00','dataPlan':'active','accessToken':'never-return'}
 def quote(self,ids,mode):
  type(self).calls+=1
  return {'NSE_EQ':{'1330':{'last_price':'123.45','accessToken':'never-return','ohlc':{'open':120,'high':125,'low':119,'close':121,'token':'never-return'}}}}
 def expiries(self,*a):return ['2026-11-26']
 def options(self,*a):return {'last_price':100,'oc':{'100':{'ce':{'oi':10,'last_price':5,'greeks':{'delta':'.5','accessToken':'never-return'}},'pe':{'oi':20,'last_price':4}},'110':{'ce':{'oi':20},'pe':{'oi':40}}}}
 def history(self,*a,**k):
  start=int(datetime(2025,10,1,3,45,tzinfo=timezone.utc).timestamp())
  return {'timestamp':[start+i*60 for i in range(65)],'open':[100+i for i in range(65)],'high':[102+i for i in range(65)],'low':[99+i for i in range(65)],'close':[101+i for i in range(65)],'volume':[10]*65}
 def trade_history(self,*a):return [{'tradingSymbol':'TEST','exchangeSegment':'NSE_EQ','exchangeTradeId':'trade1','orderId':'order1','transactionType':'BUY','tradedQuantity':2,'tradedPrice':'100.25','exchangeTime':'2025-10-01 10:00:00'}]

@pytest.fixture
def dhan(portfolio,monkeypatch):
 c,ids,aids=portfolio
 with m.DB() as s:
  for aid in aids:s.get(BrokerAccount,aid).broker='dhan'
  s.commit()
 import fakeredis
 monkeypatch.setattr(routes,'cache',fakeredis.FakeRedis())
 monkeypatch.setattr(routes,'DhanClient',FixtureClient);FixtureClient.calls=0
 return c,ids,aids


def test_sdk_account_profile_owner_mask_and_read_status(dhan):
 c,ids,aids=dhan;login(c,0)
 d=c.get('/api/v1/dhan/status').json()
 assert len(d['accounts'])==1 and d['accounts'][0]['id']==aids[0] and d['live_dhan_execution'] is False
 assert c.get('/api/v1/dhan/profile',params={'account_id':aids[1]}).status_code==404
 profile=c.get('/api/v1/dhan/profile',params={'account_id':aids[0]})
 assert profile.status_code==200 and 'never-return' not in profile.text and profile.json()['data']['client_id'].endswith('3456')


def test_personal_quote_csrf_owner_cache_and_secret_filtering(dhan):
 c,ids,aids=dhan;h=login(c,0);p={'account_id':aids[0],'security_ids':[1330],'segment':'NSE_EQ'}
 assert c.post('/api/v1/dhan/quotes',json=p).status_code==403
 assert c.post('/api/v1/dhan/quotes',json={**p,'account_id':aids[1]},headers=h).status_code==404
 first=c.post('/api/v1/dhan/quotes',json=p,headers=h);second=c.post('/api/v1/dhan/quotes',json=p,headers=h)
 assert first.status_code==second.status_code==200 and FixtureClient.calls==1
 assert first.json()['data'][0]['last_price']=='123.45' and 'never-return' not in first.text
 assert c.post('/api/v1/dhan/quotes',json={**p,'security_ids':[-1]},headers=h).status_code==422
 with m.DB() as s:
  cr=s.scalar(select(BrokerCredential).where(BrokerCredential.account_id==aids[0]));cr.expires_at=now()-timedelta(seconds=1);s.commit()
 assert c.post('/api/v1/dhan/quotes',json=p,headers=h).status_code==409


def test_option_chain_and_history_use_real_sdk_shapes(dhan):
 c,ids,aids=dhan;login(c,0);p={'account_id':aids[0],'security_id':1330,'segment':'IDX_I'}
 assert c.get('/api/v1/dhan/expiries',params=p).json()['data']==['2026-11-26']
 d=c.get('/api/v1/dhan/option-chain',params={**p,'expiry':'2026-11-26'})
 assert d.status_code==200,d.text
 assert Decimal(d.json()['data']['pcr'])==2 and 'never-return' not in d.text
 hist=c.get('/api/v1/dhan/history',params={**p,'segment':'NSE_EQ','from_date':'2025-10-01','to_date':'2025-10-02','interval':'2'})
 assert hist.status_code==200,hist.text
 rows=hist.json()['data']['candles'];assert len(rows)==33 and rows[-1]['complete'] is False
 assert rows[0]['open']=='100' and rows[0]['close']=='102' and rows[0]['volume']=='20'
 assert hist.json()['data']['research']['ml_model_status']=='NOT_CONFIGURED'
 assert c.get('/api/v1/dhan/history',params={**p,'from_date':'2025-10-02','to_date':'2025-10-01'}).status_code==422


def test_dhan_trade_history_maps_actual_execution_fields(dhan):
 c,ids,aids=dhan;login(c,0)
 r=c.get('/api/v1/dhan/trade-history',params={'account_id':aids[0],'from_date':'2025-10-01','to_date':'2025-10-02'})
 assert r.status_code==200,r.text
 row=r.json()['data'][0]
 assert row['trade_id']=='trade1' and Decimal(row['price'])==Decimal('100.25') and row['quantity']=='2'


def test_research_warmup_aggregation_and_no_execution():
 data=FixtureClient().history();series=candles(data);r=indicators(series)
 assert r['status']=='READY' and r['ema_60'] is not None and r['rsi_14']==100 and r['confidence'] is None and not r['order_submitted']
 grouped=aggregate(series,3);assert grouped[0]['high']==104 and grouped[-1]['complete'] is False
 assert indicators(series[:2])['ema_60'] is None
 with pytest.raises(DhanError):candles({'timestamp':[1],'open':[],'high':[],'low':[],'close':[]})


def test_verified_renewal_seals_token_without_returning_it(dhan,monkeypatch):
 from app.brokers.individual import verifiers
 from app.brokers.individual.verifiers import VerifiedSession
 from app.security.encryption import open_credentials
 c,ids,aids=dhan;h=login(c,0)
 monkeypatch.setattr(FixtureClient,'renew',lambda self:{'accessToken':'renewed-private-token'},raising=False)
 monkeypatch.setattr(verifiers.DhanVerifier,'validate',lambda self,c:VerifiedSession('account-0',{'access_token':c['access_token']},now()+timedelta(hours=2),'broker_reported'))
 assert c.post(f'/api/v1/dhan/accounts/{aids[0]}/renew').status_code==403
 assert c.post(f'/api/v1/dhan/accounts/{aids[1]}/renew',headers=h).status_code==404
 r=c.post(f'/api/v1/dhan/accounts/{aids[0]}/renew',headers=h)
 assert r.status_code==200,r.text
 assert 'renewed-private-token' not in r.text
 with m.DB() as s:
  cr=s.scalar(select(BrokerCredential).where(BrokerCredential.account_id==aids[0]));data=open_credentials(ids[0],aids[0],cr.ciphertext)
  assert data['credentials']['access_token']=='renewed-private-token' and 'renewed-private-token' not in cr.ciphertext
  from app.execution.models import LiveOrder
  assert s.scalar(select(func.count()).select_from(LiveOrder))==0
