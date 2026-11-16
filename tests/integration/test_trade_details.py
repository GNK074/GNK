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
