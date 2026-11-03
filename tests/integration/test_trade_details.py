from test_auth import client
from test_multi_user import three,login
from app import main as m
from app.core.config import now
from app.execution.models import LiveOrder
from app.trade_details.models import TradeSignal
from app.market_data.models import MarketInstrument
from app.models.trading import Strategy
from app.market_data.config import market_settings as cfg
from sqlalchemy import select,func
from datetime import datetime,timezone
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import pytest

@pytest.fixture
def reports(three):
 c,ids,accounts=three
 with m.DB() as s:
  strategies=[]
  instrument=MarketInstrument(provider='upstox',instrument_key='NSE_EQ|TEST',exchange='NSE',segment='NSE_EQ',symbol='TEST',name='Fixture',instrument_type='EQ',lot_size=1,tick_size=5,status='ACTIVE',version='fixture');s.add(instrument);s.flush();iid=instrument.id
  for uid in ids:
   strategy=Strategy(user_id=uid,name='Service '+uid[:5]);s.add(strategy);s.flush();strategies.append(strategy.id)
  s.commit()
 return c,ids,accounts,strategies,iid

def add_order(reports,user=0,side='BUY',qty=2,price='100',filled=None,status='FILLED',day=1,minute=15,reason=None,stamp=True):
 c,ids,accounts,strategies,iid=reports
 fill=qty if filled is None else filled
 with m.DB() as s:
  row=LiveOrder(user_id=ids[user],account_id=accounts[user],strategy_id=strategies[user],instrument_id=iid,instrument_key='NSE_EQ|TEST',symbol='TEST',side=side,quantity=qty,price=Decimal(price),status=status,tag='tag'+str(__import__('uuid').uuid4()),idempotency_key=str(__import__('uuid').uuid4()),request_hash='hash',filled_quantity=fill,average_price=Decimal(price) if fill else None,fills=[{'trade_id':str(__import__('uuid').uuid4()),'quantity':fill,'price':price,'exchange_timestamp':f'2025-10-{day:02d}T09:{minute:02d}:00+05:30' if stamp else ''}] if fill else [],created_at=datetime(2025,10,day,3,minute,tzinfo=timezone.utc),reconciled_at=now(),error_code=reason)
  s.add(row);s.commit();return row.id

def test_empty_tables_and_options_are_owned(reports):
 c,ids,accounts,strategies,iid=reports;login(c,0)
 for path in ('orders','client-trade-history','signals'):
  r=c.get('/api/v1/tradedetails/'+path);assert r.status_code==200,r.text
  assert r.json()['items']==[] and r.json()['total']==0
 options=c.get('/api/v1/tradedetails/options').json()
 assert [a['id'] for a in options['accounts']]==[accounts[0]]
 assert {x['id'] for x in options['strategies']}=={strategies[0]}
 assert 'BANKNIFTY' in options['scripts']

def test_reporting_isolation_filters_pagination_sort_and_detail(reports):
 c,ids,accounts,strategies,iid=reports
 own=add_order(reports,filled=0,status='OPEN');foreign=add_order(reports,user=1)
 add_order(reports,filled=0,status='PENDING',day=2);add_order(reports,filled=0,status='REJECTED',day=3,reason='TRADING_TOKEN_REJECTED')
 login(c,0)
 r=c.get('/api/v1/tradedetails/orders',params={'bucket':'ALL','page_size':1,'sort':'entry_time','direction':'asc'})
 assert r.status_code==200,r.text
 assert r.json()['total']==3 and r.json()['pages']==3 and r.json()['items'][0]['id']==own
 assert c.get('/api/v1/tradedetails/orders',params={'bucket':'FAILED'}).json()['total']==1
 assert c.get('/api/v1/tradedetails/orders',params={'bucket':'ALL','q':'TOKEN'}).json()['total']==1
 assert c.get('/api/v1/tradedetails/orders',params={'bucket':'ALL','strategy_id':strategies[1]}).json()['total']==0
 assert c.get('/api/v1/tradedetails/orders/'+foreign).status_code==404
 assert c.get('/api/v1/tradedetails/orders/'+own).status_code==200
 assert c.get('/api/v1/tradedetails/orders',params={'bucket':'ALL','sort':'password'}).status_code==422
 assert c.get('/api/v1/tradedetails/orders',params={'bucket':'ALL','page_size':101}).status_code==422
 assert c.get('/api/v1/tradedetails/client-trade-history',params={'status':'unauthorized'}).json()['total']==1
 assert 'private-token' not in r.text

def test_fifo_partial_and_complete_history_uses_reconciled_fills(reports):
 c,ids,accounts,strategies,iid=reports
 entry=add_order(reports,qty=3,price='100');exit1=add_order(reports,side='SELL',qty=1,price='110',minute=20)
 login(c,0)
 rows=c.get('/api/v1/tradedetails/client-trade-history').json()['items'];assert len(rows)==1
 row=rows[0];assert row['id']==entry and row['entry_qty']==3 and row['exit_qty']==1 and row['open_qty']==2
 assert Decimal(row['pnl'])==10 and row['trade_status']=='PARTIALLY_CLOSED' and row['exit_order_ids']==[exit1]
 add_order(reports,side='SELL',qty=2,price='105',minute=25)
 row=c.get('/api/v1/tradedetails/client-trade-history').json()['items'][0]
 assert row['exit_qty']==3 and row['open_qty']==0 and Decimal(row['pnl'])==20 and row['trade_status']=='CLOSED'
 assert c.get('/api/v1/tradedetails/client-trade-history',params={'from_date':'2025-10-02'}).json()['total']==0
 assert c.get('/api/v1/tradedetails/client-trade-history',params={'from_date':'2025-10-03','to_date':'2025-10-01'}).status_code==422

def test_unknown_basis_and_missing_timestamps_never_fabricate_pnl(reports):
 c,ids,accounts,strategies,iid=reports
 add_order(reports,side='SELL',price='110');login(c,0)
 row=c.get('/api/v1/tradedetails/client-trade-history').json()['items'][0]
 assert row['entry_price'] is None and row['pnl'] is None and row['trade_status']=='UNKNOWN'
 add_order(reports,price='100',day=2,stamp=False)
 row=next(r for r in c.get('/api/v1/tradedetails/client-trade-history').json()['items'] if r['entry_qty'])
 assert row['pnl'] is None and row['price'] is None
 assert c.get('/api/v1/tradedetails/orders',params={'bucket':'ALL'}).json()['summary']['running_pnl'] is None

def test_fifo_remaining_cost_uses_remaining_lots_not_original_average(reports,monkeypatch):
 import app.trade_details.service as service
 c,ids,accounts,strategies,iid=reports
 add_order(reports,qty=1,price='100',minute=15)
 later=add_order(reports,qty=1,price='120',minute=16)
 add_order(reports,side='SELL',qty=1,price='130',minute=17)
 monkeypatch.setattr(service,'cached_prices',lambda *args:{'NSE_EQ|TEST':{'ltp':125,'data_status':'LIVE'}})
 login(c,0);data=c.get('/api/v1/tradedetails/orders',params={'bucket':'ALL'}).json()
 assert Decimal(data['summary']['running_pnl'])==5
 row=next(x for x in data['items'] if x['id']==later);assert Decimal(row['pnl'])==5

def test_signal_creation_is_persisted_owned_and_does_not_place_order(reports,monkeypatch):
 import app.trade_details.routes as routes
 c,ids,accounts,strategies,iid=reports
 monkeypatch.setattr(routes,'available_instrument',lambda *args:None)
 h=login(c,0)
 data={'strategy_id':strategies[0],'account_id':accounts[0],'instrument_id':iid,'side':'BUY','quantity':1,'order_type':'LIMIT','reference_price':'100','note':'Manual research signal'}
 assert c.post('/api/v1/tradedetails/signals',json=data).status_code==403
 result=c.post('/api/v1/tradedetails/signals',json=data,headers=h);assert result.status_code==201,result.text
 sid=result.json()['id'];assert result.json()['execution']=='SIGNAL_ONLY_NO_ORDER_SUBMITTED'
 assert c.get('/api/v1/tradedetails/signals',params={'q':'TEST'}).json()['total']==1
 with m.DB() as s:assert s.scalar(select(func.count()).select_from(LiveOrder))==0
 h=login(c,1)
 assert c.get('/api/v1/tradedetails/signals/'+sid).status_code==404
 assert c.get('/api/v1/tradedetails/signals').json()['total']==0
 assert c.post('/api/v1/tradedetails/signals',json=data,headers=h).status_code==404

def test_excel_export_is_real_xlsx_scoped_and_does_not_execute_formulas(reports):
 c,ids,accounts,strategies,iid=reports
 add_order(reports,user=0);add_order(reports,user=1)
 with m.DB() as s:s.get(Strategy,strategies[0]).name='=HYPERLINK("unsafe")';s.commit()
 login(c,0)
 response=c.get('/api/v1/tradedetails/client-trade-history/export');assert response.status_code==200
 assert 'spreadsheetml.sheet' in response.headers['content-type']
 with ZipFile(BytesIO(response.content)) as z:
  ET.fromstring(z.read('[Content_Types].xml'))
  sheet=ET.fromstring(z.read('xl/worksheets/sheet1.xml'));ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
  assert len(sheet.findall('s:sheetData/s:row',ns))==2
  assert not sheet.findall('.//s:f',ns)
  strings=[x.text for x in sheet.findall('.//s:t',ns)]
  assert '=HYPERLINK("unsafe")' in strings

def test_new_order_records_one_signal_despite_idempotent_retry(live_setup):
 c,ids,accounts,h,p=live_setup
 first=c.post('/api/v1/live/orders',json=p,headers=h);second=c.post('/api/v1/live/orders',json=p,headers=h)
 assert first.status_code==200 and second.status_code==200
 with m.DB() as s:
  rows=list(s.scalars(select(TradeSignal).where(TradeSignal.user_id==ids[0])))
  assert len(rows)==1 and rows[0].source_order_id==first.json()['id'] and rows[0].source=='ORDER_REQUEST'

from test_live_execution import live_setup
