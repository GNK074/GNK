from test_auth import client
from test_multi_user import three,login
from app import main as m
from app.portfolio import service as svc
from app.portfolio.adapters import ADAPTERS,normalize,PortfolioError,Upstox
from app.portfolio.models import PortfolioSnapshot,PortfolioSync
from app.models.trading import BrokerAccount,BrokerCredential
from app.core.config import now
from app.security.encryption import seal_credentials
from sqlalchemy import select,func
from datetime import timedelta
from decimal import Decimal
import pytest,fakeredis,httpx,copy

@pytest.fixture
def portfolio(three,monkeypatch):
 c,ids,aids=three
 monkeypatch.setattr(svc,'cache',fakeredis.FakeRedis())
 with m.DB() as s:
  for uid,aid in zip(ids,aids):
   credential=s.scalar(select(BrokerCredential).where(BrokerCredential.account_id==aid));credential.expires_at=now()+timedelta(hours=2)
  s.commit()
 return three

def put(uid,aid,kind,data,age=0):
 with m.DB() as s:
  c=s.scalar(select(BrokerCredential).where(BrokerCredential.account_id==aid))
  snap=s.scalar(select(PortfolioSnapshot).where(PortfolioSnapshot.account_id==aid,PortfolioSnapshot.kind==kind))
  if not snap:snap=PortfolioSnapshot(user_id=uid,account_id=aid,kind=kind);s.add(snap)
  snap.rows=svc.serialized(data);snap.fetched_at=now()-timedelta(seconds=age);snap.credential_version=svc.version(c);s.commit()

def holding(symbol='ABC',isin='INE000000001',qty='2',price='110'):
 return normalize('upstox','holdings',[dict(trading_symbol=symbol,isin=isin,instrument_type='EQ',quantity=qty,average_price='100',last_price=price,exchange='NSE')])

def test_owned_empty_refresh_csrf_and_throttle(portfolio):
 c,ids,aids=portfolio;h=login(c,0)
 assert c.get('/api/v1/portfolio/holdings').json()['items']==[]
 assert c.get('/api/v1/portfolio/summary').json()['holdings_current']['value'] is None
 assert [a['id'] for a in c.get('/api/v1/portfolio/accounts').json()['items']]==[aids[0]]
 assert c.post('/api/v1/portfolio/refresh',json={}).status_code==403
 assert c.post('/api/v1/portfolio/refresh',json={'account_id':aids[1]},headers=h).status_code==404
 assert c.post('/api/v1/portfolio/refresh',json={},headers=h).json()['queued']==[aids[0]]
 assert c.post('/api/v1/portfolio/refresh',json={},headers=h).json()['queued']==[]


def test_summary_precision_separation_and_filters(portfolio):
 c,ids,aids=portfolio;login(c,0)
 put(ids[0],aids[0],'holdings',holding());put(ids[0],aids[0],'positions',normalize('upstox','positions',[dict(trading_symbol='ABC',quantity=2,realised='5.25',unrealised='20',average_price=100,last_price=110)]))
 put(ids[0],aids[0],'funds',[dict(segment='SEC',available='250',currency='INR')])
 put(ids[1],aids[1],'holdings',holding(qty='100'))
 d=c.get('/api/v1/portfolio/summary').json()
 assert Decimal(d['holdings_current']['value'])==220 and Decimal(d['holdings_pnl']['value'])==20
 assert Decimal(d['positions_realized']['value'])==Decimal('5.25')
 assert 'net_worth' not in d
 assert c.get('/api/v1/portfolio/holdings',params={'account_id':aids[1]}).json()['total']==0
 assert c.get('/api/v1/portfolio/holdings',params={'q':'NONEXISTENT'}).json()['total']==0
 assert c.get('/api/v1/portfolio/funds',params={'exchange':'NSE','q':'ABC'}).json()['total']==1
 assert 'private-token' not in str(d)
 assert c.get('/api/v1/portfolio/holdings',params={'sort':'password'}).status_code==422
 assert c.get('/api/v1/portfolio/holdings',params={'page_size':101}).status_code==422


def test_missing_stale_expired_and_reconnected_snapshots(portfolio):
 c,ids,aids=portfolio;login(c,0)
 put(ids[0],aids[0],'holdings',holding(price=None));d=c.get('/api/v1/portfolio/summary').json()
 assert d['holdings_current']['value'] is None and not d['holdings_current']['complete']
 put(ids[0],aids[0],'holdings',holding(),age=200)
 assert c.get('/api/v1/portfolio/holdings').json()['items'][0]['price_status']=='STALE_SNAPSHOT'
 assert c.get('/api/v1/portfolio/summary').json()['holdings_current']['value'] is None
 with m.DB() as s:
  cr=s.scalar(select(BrokerCredential).where(BrokerCredential.account_id==aids[0]));cr.expires_at=now()-timedelta(seconds=1);s.commit()
 assert c.get('/api/v1/portfolio/accounts').json()['items'][0]['status']=='SESSION_EXPIRED'
 with m.DB() as s:
  cr=s.scalar(select(BrokerCredential).where(BrokerCredential.account_id==aids[0]));cr.ciphertext=seal_credentials(ids[0],aids[0],{'access_token':'replacement'});s.commit()
 assert c.get('/api/v1/portfolio/holdings').json()['items']==[]


def test_isin_consolidation_keeps_components_and_unknowns(portfolio):
 c,ids,aids=portfolio;login(c,0)
 with m.DB() as s:
  a=BrokerAccount(user_id=ids[0],broker='dhan',account_identifier='other-owned',status='connected');s.add(a);s.flush();aid=a.id;s.add(BrokerCredential(user_id=ids[0],account_id=aid,ciphertext='fixture',key_version='v1',expires_at=now()+timedelta(hours=1)));s.commit()
 put(ids[0],aids[0],'holdings',holding());put(ids[0],aid,'holdings',holding(qty='3',price='120'))
 r=c.get('/api/v1/portfolio/holdings',params={'consolidated':True}).json();assert r['total']==1
 row=r['items'][0];assert Decimal(row['quantity'])==5 and Decimal(row['current_value'])==580 and len(row['components'])==2
 put(ids[0],aid,'holdings',holding(isin='INE000000002'))
 assert c.get('/api/v1/portfolio/holdings',params={'consolidated':True}).json()['total']==2
 put(ids[0],aid,'holdings',holding(isin='INF000000001'))
 assert c.get('/api/v1/portfolio/holdings',params={'consolidated':True}).json()['total']==2

class FixtureAdapter:
 error_kind=None
 def fetch(self,k):
  if k==self.error_kind:raise PortfolioError('INVALID_RESPONSE')
  return holding() if k=='holdings' else [dict(segment='SEC',available='200')] if k=='funds' else []

def test_sync_idempotent_partial_failures_and_no_trading(portfolio,monkeypatch):
 c,ids,aids=portfolio;monkeypatch.setattr(svc,'build_adapter',lambda *a:FixtureAdapter())
 FixtureAdapter.error_kind=None
 assert svc.sync_account(ids[0],aids[0])
 with m.DB() as s:
  assert s.scalar(select(func.count()).select_from(PortfolioSnapshot))==5
  st=s.scalar(select(PortfolioSync));st.next_attempt_at=now()-timedelta(seconds=1);s.commit()
 FixtureAdapter.error_kind='holdings'
 assert svc.sync_account(ids[0],aids[0])
 with m.DB() as s:
  assert s.scalar(select(func.count()).select_from(PortfolioSnapshot))==5
  st=s.scalar(select(PortfolioSync));assert st.errors=={'holdings':'INVALID_RESPONSE'}
  assert s.scalar(select(PortfolioSnapshot).where(PortfolioSnapshot.kind=='holdings')).rows[0]['symbol']=='ABC'
  from app.execution.models import LiveOrder
  from app.models.trading import Order
  assert s.scalar(select(func.count()).select_from(LiveOrder))==0 and s.scalar(select(func.count()).select_from(Order))==0
 login(c,0)
 assert c.get('/api/v1/portfolio/holdings').json()['coverage'][0]['fresh'] is False
 assert c.get('/api/v1/portfolio/summary').json()['holdings_current']['value'] is None


def test_lock_backoff_and_credential_change_fence(portfolio,monkeypatch):
 c,ids,aids=portfolio;key=f'gnk:portfolio:lock:{ids[0]}:{aids[0]}'
 svc.cache.set(key,'another-worker',ex=300)
 monkeypatch.setattr(svc,'build_adapter',lambda *a:FixtureAdapter())
 assert not svc.sync_account(ids[0],aids[0]);svc.cache.delete(key)
 class Changed:
  def fetch(self,k):
   with m.DB() as s:
    cr=s.scalar(select(BrokerCredential).where(BrokerCredential.account_id==aids[0]));cr.ciphertext='changed';s.commit()
   return holding()
 monkeypatch.setattr(svc,'build_adapter',lambda *a:Changed())
 assert not svc.sync_account(ids[0],aids[0])
 with m.DB() as s:assert s.scalar(select(func.count()).select_from(PortfolioSnapshot))==0


def test_export_owned_and_safe_text(portfolio):
 from zipfile import ZipFile
 from io import BytesIO
 c,ids,aids=portfolio;login(c,0)
 put(ids[0],aids[0],'holdings',holding(symbol='=FORMULA'));put(ids[1],aids[1],'holdings',holding(symbol='FOREIGN'))
 r=c.get('/api/v1/portfolio/holdings/export');assert r.status_code==200
 with ZipFile(BytesIO(r.content)) as z:
  xml=z.read('xl/worksheets/sheet1.xml').decode();assert '=FORMULA' in xml and '<f>' not in xml and 'FOREIGN' not in xml

@pytest.mark.parametrize('broker,envelope',[
 ('upstox',{'status':'success','data':[{'trading_symbol':'ABC','quantity':2,'average_price':'10.25','last_price':'11.30'}]}),
 ('zerodha',{'status':'success','data':[{'tradingsymbol':'ABC','quantity':1,'t1_quantity':1,'average_price':'10.25','last_price':'11.30'}]}),
 ('dhan',[{'tradingSymbol':'ABC','totalQty':2,'avgCostPrice':'10.25','lastPrice':'11.30'}]),
 ('angelone',{'status':True,'data':[{'tradingsymbol':'ABC','quantity':2,'averageprice':'10.25','ltp':'11.30'}]}),
 ('fyers',{'s':'ok','holdings':[{'symbol':'NSE:ABC-EQ','remainingQuantity':2,'costPrice':'10.25','ltp':'11.30'}]}),
 ('5paisa',{'head':{'status':'0'},'body':{'Status':0,'Data':[{'Symbol':'ABC','Quantity':2,'AvgRate':'10.25','CurrentPrice':'11.30'}]}})
])
def test_six_readonly_adapter_contracts(broker,envelope,monkeypatch):
 from app.core.config import settings
 monkeypatch.setattr(settings,'broker_egress_ip','130.210.34.12')
 calls=[]
 def handler(req):calls.append(req);return httpx.Response(200,json=envelope)
 a=ADAPTERS[broker]({'api_key':'key','app_key':'key','app_id':'app','access_token':'token','jwt_token':'jwt'},'account',transport=httpx.MockTransport(handler),sleep=lambda _:None)
 data=a.fetch('holdings');assert data[0]['quantity']==2 and data[0]['invested_value']==Decimal('20.50')
 assert data[0]['current_value']==Decimal('22.60') and data[0]['pnl']==Decimal('2.10')
 assert calls[0].method==('POST' if broker=='5paisa' else 'GET')
 assert not any(x in calls[0].url.path.lower() for x in ('placeorder','modify','cancel','exit'))


def test_transport_retries_only_bounded_reads_and_redacts():
 count=0
 def handler(r):
  nonlocal count
  count+=1;return httpx.Response(503)
 a=Upstox({'access_token':'private'},'a',transport=httpx.MockTransport(handler),sleep=lambda _:None)
 with pytest.raises(PortfolioError,match='BROKER_UNAVAILABLE'):a.fetch('holdings')
 assert count==2
 count=0
 def authfail(r):
  nonlocal count
  count+=1;return httpx.Response(401,json={'secret':'private'})
 a.transport=httpx.MockTransport(authfail)
 with pytest.raises(PortfolioError,match='SESSION_EXPIRED'):a.fetch('holdings')
 assert count==1
 with pytest.raises(PortfolioError):normalize('upstox','positions',[{'symbol':'ABC','quantity':'NaN'}])

@pytest.mark.parametrize('broker,data',[
 ('upstox',{'trading_symbol':'TEST','quantity':-2,'realised':'2.25','unrealised':'-5.75','average_price':100}),
 ('zerodha',{'tradingsymbol':'TEST','quantity':-2,'realised':'2.25','unrealised':'-5.75','average_price':100}),
 ('dhan',{'tradingSymbol':'TEST','netQty':-2,'realizedProfit':'2.25','unrealizedProfit':'-5.75','costPrice':100}),
 ('angelone',{'tradingsymbol':'TEST','netqty':-2,'realised':'2.25','unrealised':'-5.75','avgnetprice':100}),
 ('fyers',{'symbol':'NSE:TEST-EQ','netQty':-2,'realized_profit':'2.25','unrealized_profit':'-5.75','netAvg':100}),
 ('5paisa',{'ScripName':'TEST','NetQty':-2,'BookedPL':'2.25','MTOM':'-5.75'})
])
def test_position_contracts_keep_reported_quantities_and_missing_basis(broker,data):
 row=normalize(broker,'positions',[data])[0]
 assert row['net_quantity']==-2 and row['realized_pnl']==Decimal('2.25')
 if broker=='5paisa':
  # MTOM's exact basis is not inferred; unavailable decomposition stays unknown.
  assert row['unrealized_pnl'] is None and row['average_price'] is None
 else:assert row['unrealized_pnl']==Decimal('-5.75') and row['total_pnl']==Decimal('-3.50') and row['average_price']==100

@pytest.mark.parametrize('broker,data,available',[
 ('upstox',{'equity':{'available_margin':'100.25','used_margin':10}},'100.25'),
 ('zerodha',{'equity':{'net':'100.25','available':{'cash':'80'},'utilised':{'debits':10}}},'100.25'),
 ('dhan',{'availabelBalance':'100.25','utilizedAmount':10},'100.25'),
 ('angelone',{'net':'100.25','availablecash':80,'utiliseddebits':10},'100.25'),
 ('fyers',[{'title':'Available Balance','equityAmount':'100.25','commodityAmount':0},{'title':'Utilized Amount','equityAmount':10,'commodityAmount':0}],'100.25'),
 ('5paisa',[{'NetAvailableMargin':'100.25','MarginUtilized':10,'Ledgerbalance':80}],'100.25')
])
def test_funds_contracts_keep_ledgers_separate(broker,data,available):
 row=normalize(broker,'funds',data)[0]
 assert row['available']==Decimal(available) and row['used_margin']==10


def test_disconnected_snapshot_retained_without_trading_credentials(portfolio):
 c,ids,aids=portfolio;login(c,0);put(ids[0],aids[0],'holdings',holding())
 with m.DB() as s:
  a=s.get(BrokerAccount,aids[0]);a.status='disconnected'
  cr=s.scalar(select(BrokerCredential).where(BrokerCredential.account_id==a.id));s.delete(cr);s.commit()
 r=c.get('/api/v1/portfolio/holdings').json()
 assert r['total']==1 and r['items'][0]['price_status']=='STALE_SNAPSHOT' and r['coverage'][0]['status']=='DISCONNECTED'
 assert c.get('/api/v1/portfolio/summary').json()['holdings_current']['value'] is None


def test_expired_token_does_not_invoke_transport(portfolio,monkeypatch):
 c,ids,aids=portfolio
 with m.DB() as s:
  cr=s.scalar(select(BrokerCredential).where(BrokerCredential.account_id==aids[0]));cr.expires_at=now()-timedelta(seconds=1);s.commit()
 monkeypatch.setattr(svc,'build_adapter',lambda *a:pytest.fail('Expired credential reached broker adapter'))
 assert not svc.sync_account(ids[0],aids[0])
 with m.DB() as s:assert s.scalar(select(PortfolioSync)).state=='SESSION_EXPIRED'

def test_equity_classification_requires_type_or_master(portfolio):
 from app.market_data.models import MarketInstrument
 c,ids,aids=portfolio
 raw=[{'trading_symbol':'UNKNOWN-DEBT','isin':'INE000000001','quantity':2,'average_price':100,'last_price':110}]
 data=normalize('upstox','holdings',raw)
 assert data[0]['asset_class']=='UNKNOWN'
 with m.DB() as s:
  assert svc.classify_holdings(s,data)[0]['asset_class']=='UNKNOWN'
  s.add(MarketInstrument(provider='upstox',instrument_key='NSE_EQ|INE000000001',exchange='NSE',segment='NSE_EQ',symbol='ABC',name='Fixture equity',instrument_type='EQ',status='ACTIVE',version='test'));s.commit()
  data=svc.classify_holdings(s,data)
  assert data[0]['asset_class']=='EQUITY' and data[0]['classification_source']=='INSTRUMENT_MASTER'


def test_rate_limit_stops_without_retry():
 calls=[]
 def handler(r):calls.append(r);return httpx.Response(429,json={'token':'do-not-echo'})
 a=Upstox({'access_token':'do-not-echo'},'a',transport=httpx.MockTransport(handler),sleep=lambda _:None)
 with pytest.raises(PortfolioError,match='RATE_LIMITED'):a.fetch('holdings')
 assert len(calls)==1

def test_first_dhan_worker_sync_classifies_before_snapshot_insert(portfolio,monkeypatch):
 from app.portfolio import worker
 from app.portfolio.adapters import Dhan
 c,ids,aids=portfolio
 with m.DB() as s:
  a=s.get(BrokerAccount,aids[0]);a.broker='dhan';s.commit()
 def handler(request):
  path=request.url.path.rsplit('/',1)[-1]
  if path=='holdings':return httpx.Response(200,json=[{'exchange':'ALL','tradingSymbol':'HDFC','securityId':'1330','isin':'INE001A01036','totalQty':10,'avgCostPrice':'2655'}])
  if path=='fundlimit':return httpx.Response(200,json={'availabelBalance':'500.25','utilizedAmount':'25'})
  return httpx.Response(200,json=[])
 monkeypatch.setattr(svc,'build_adapter',lambda a,cr:Dhan({'access_token':'fixture-token'},a.account_identifier,transport=httpx.MockTransport(handler),sleep=lambda _:None))
 monkeypatch.setattr(worker,'cache',svc.cache)
 # Exercise the actual discovery loop, not only the normalizer.
 worker.run_once()
 with m.DB() as s:
  snapshots=list(s.scalars(select(PortfolioSnapshot).where(PortfolioSnapshot.account_id==aids[0])))
  assert len(snapshots)==5
  holding_snapshot=next(r for r in snapshots if r.kind=='holdings')
  assert holding_snapshot.rows[0]['symbol']=='HDFC'
  assert Decimal(holding_snapshot.rows[0]['invested_value'])==26550
  assert holding_snapshot.rows[0]['current_value'] is None
  state=s.scalar(select(PortfolioSync).where(PortfolioSync.account_id==aids[0]))
  assert state.state=='CONNECTED' and state.errors=={}

def test_unexpected_sync_failure_has_safe_error_backoff_and_retains_snapshot(portfolio,monkeypatch,capsys):
 from app.portfolio import worker
 c,ids,aids=portfolio
 put(ids[0],aids[0],'holdings',holding())
 with m.DB() as s:
  for aid in aids[1:]:s.get(BrokerAccount,aid).status='disconnected'
  s.commit()
 calls=[]
 class BrokenAdapter:
  def fetch(self,kind):calls.append(kind);return holding()
 def broken_classification(*args):raise RuntimeError('sensitive-token-and-broker-payload')
 monkeypatch.setattr(svc,'build_adapter',lambda *a:BrokenAdapter())
 monkeypatch.setattr(svc,'classify_holdings',broken_classification)
 monkeypatch.setattr(worker,'cache',svc.cache)
 worker.run_once()
 output=capsys.readouterr().out
 assert 'Code: INTERNAL_SYNC_ERROR' in output and 'sensitive-token' not in output
 with m.DB() as s:
  state=s.scalar(select(PortfolioSync).where(PortfolioSync.account_id==aids[0]))
  assert state.state=='ERROR' and state.errors=={'sync':'INTERNAL_SYNC_ERROR'}
  assert svc.utc(state.next_attempt_at)>now()
  snap=s.scalar(select(PortfolioSnapshot).where(PortfolioSnapshot.account_id==aids[0]))
  assert snap.rows[0]['symbol']=='ABC'
 worker.run_once();assert calls==['holdings']
 login(c,0)
 assert c.get('/api/v1/portfolio/holdings').json()['coverage'][0]['fresh'] is False
 assert c.get('/api/v1/portfolio/accounts').json()['items'][0]['errors']=={'sync':'INTERNAL_SYNC_ERROR'}
