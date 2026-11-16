"""GNK workflows use fake broker HTTP/socket transports; never real orders."""
from test_auth import client
from test_multi_user import three,login
from test_live_execution import live_setup,Broker
from app import main as m
from app.core.config import settings,now
from app.brokers.dhan import instruments,streams
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
