from pathlib import Path
from datetime import datetime,timezone
import os,subprocess,sys
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
from app.models.identity import User
from app.models.trading import BrokerAccount,Strategy
from app.market_data.models import MarketInstrument
from app.execution.models import LiveOrder
from app.trade_details.models import TradeSignal

def test_0007_to_head_backfills_real_order_signals_once(tmp_path):
 root=Path(__file__).resolve().parents[2];url='sqlite:///'+(tmp_path/'signal-upgrade.db').as_posix()
 env={**os.environ,'APP_ENV':'testing','ENVIRONMENT':'testing','DATABASE_URL':url,'PYTHONPATH':str(root/'backend'),'STARTUP_CONNECTIVITY_CHECK':'false'}
 cmd=[sys.executable,'-m','alembic','-c',str(root/'backend/alembic.ini'),'upgrade']
 subprocess.run(cmd+['0007'],cwd=root,env=env,check=True,capture_output=True)
 engine=create_engine(url)
 with Session(engine) as s:
  user=User(name='Existing trader',email='existing@example.com',password='preserved',verified=True);s.add(user);s.flush()
  strategy=Strategy(user_id=user.id,name='Existing strategy');account=BrokerAccount(user_id=user.id,broker='upstox',account_identifier='existing-account');instrument=MarketInstrument(provider='upstox',instrument_key='NSE_EQ|OLD',exchange='NSE',segment='NSE_EQ',symbol='OLD',name='Existing instrument',instrument_type='EQ',status='ACTIVE',version='old');s.add_all([strategy,account,instrument]);s.flush()
  stamp=datetime(2025,10,1,3,45,tzinfo=timezone.utc)
  order=LiveOrder(user_id=user.id,account_id=account.id,strategy_id=strategy.id,instrument_id=instrument.id,instrument_key=instrument.instrument_key,symbol=instrument.symbol,side='BUY',quantity=1,price=100,tag='existing-order',idempotency_key='old-key',request_hash='hash',created_at=stamp);s.add(order);s.commit();oid=order.id;uid=user.id
 subprocess.run(cmd+['head'],cwd=root,env=env,check=True,capture_output=True)
 subprocess.run(cmd+['head'],cwd=root,env=env,check=True,capture_output=True)
 with Session(engine) as s:
  assert s.scalar(select(func.count()).select_from(TradeSignal))==1
  signal=s.scalar(select(TradeSignal))
  assert signal.source_order_id==oid and signal.user_id==uid and signal.source=='ORDER_REQUEST'
  assert signal.signal_time.replace(tzinfo=timezone.utc)==stamp
  assert s.get(LiveOrder,oid).status=='SUBMITTING' and s.get(User,uid).password=='preserved'
 engine.dispose()
