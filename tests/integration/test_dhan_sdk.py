from test_auth import client
from test_multi_user import three,login
from app import main as m
from app.core.config import now
from app.brokers.dhan.client import DhanClient,DhanError,SDK_VERSION
from app.brokers.dhan.analytics import candles,aggregate,indicators
from app.models.trading import BrokerAccount,BrokerCredential
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


def test_research_warmup_aggregation_and_no_execution():
 data=FixtureClient().history();series=candles(data);r=indicators(series)
 assert r['status']=='READY' and r['ema_60'] is not None and r['rsi_14']==100 and r['confidence'] is None and not r['order_submitted']
 grouped=aggregate(series,3);assert grouped[0]['high']==104 and grouped[-1]['complete'] is False
 assert indicators(series[:2])['ema_60'] is None
 with pytest.raises(DhanError):candles({'timestamp':[1],'open':[],'high':[],'low':[],'close':[]})
