"""Readiness explains existing gates and never mutates approval or broker state."""
from test_auth import client
from test_multi_user import three,login
from test_live_execution import live_setup,Broker
from app import main as m
from app.core.config import settings,now
from app.execution import live_service as live
from app.models.trading import BrokerAccount,BrokerCredential,PlatformControl,Strategy,RiskConfiguration
from app.execution.models import LiveOrder
from app.security.encryption import seal_credentials
from sqlalchemy import select,func
from datetime import timedelta
import pytest

@pytest.fixture
def activation(live_setup):
 c,ids,aids,h,p=live_setup
 with m.DB() as s:
  cr=s.scalar(select(BrokerCredential).where(BrokerCredential.account_id==aids[0]))
  cr.expires_at=now()+timedelta(hours=1)
  cr.ciphertext=seal_credentials(ids[0],aids[0],{'connection_method':'individual_credentials','credentials':{'access_token':'fake-only'}})
  s.commit()
 return c,ids,aids,h,p

def test_ready_account_reports_enabled_without_sending_or_arming(activation):
 c,ids,aids,h,p=activation
 r=c.get('/api/v1/live/readiness');assert r.status_code==200,r.text
 data=r.json();assert data['placement_ready'] is True and data['accounts'][0]['placement_ready'] is True
 assert data['accounts'][0]['blockers']==[] and 'fake-only' not in r.text
 assert Broker.calls==0
 with m.DB() as s:assert s.scalar(select(func.count()).select_from(LiveOrder))==0

@pytest.mark.parametrize('failure,code',[('session','BROKER_SESSION'),('account','ACCOUNT_AUTHORIZATION'),('armed','ACCOUNT_ARMED'),('platform','PLATFORM_STOP'),('strategy','APPROVED_STRATEGY'),('risk','PERSONAL_STOP')])
def test_each_failed_existing_gate_locks_readiness(activation,failure,code):
 c,ids,aids,h,p=activation
 with m.DB() as s:
  if failure=='session':s.scalar(select(BrokerCredential).where(BrokerCredential.account_id==aids[0])).expires_at=now()-timedelta(seconds=1)
  if failure=='account':s.get(BrokerAccount,aids[0]).live_authorized=False
  if failure=='armed':s.get(BrokerAccount,aids[0]).kill_switch=True
  if failure=='platform':s.get(PlatformControl,'global').kill_switch=True
  if failure=='strategy':s.get(Strategy,p['strategy_id']).approved=False
  if failure=='risk':s.add(RiskConfiguration(user_id=ids[0],kill_switch=True))
  s.commit()
 data=c.get('/api/v1/live/readiness').json()
 assert not data['placement_ready']
 assert code in [c['code'] for c in data['accounts'][0]['blockers']]
 assert Broker.calls==0

def test_activation_explains_disabled_dhan_flag_and_owner_isolation(activation,monkeypatch):
 c,ids,aids,h,p=activation
 with m.DB() as s:s.get(BrokerAccount,aids[0]).broker='dhan';s.commit()
 monkeypatch.setattr(live,'broker_approved',lambda s,broker='upstox':True)
 monkeypatch.setattr(settings,'dhan_execution_enabled',False)
 data=c.get('/api/v1/live/readiness?broker=dhan').json()
 assert not data['placement_ready']
 assert 'DHAN_EXECUTION_ENABLED' in next(c['action'] for c in data['checks'] if c['code']=='SERVER_ACTIVATION')
 monkeypatch.setattr(settings,'dhan_execution_enabled',True)
 assert c.get('/api/v1/live/readiness?broker=dhan').json()['placement_ready'] is True
 login(c,1)
 data=c.get('/api/v1/live/readiness?broker=dhan').json()
 assert data['accounts']==[] and not data['placement_ready'] and aids[0] not in str(data)

def test_reconciliation_and_approval_status_are_not_cosmetic(activation,monkeypatch):
 c,ids,aids,h,p=activation
 monkeypatch.setattr(live,'broker_approved',lambda s:False)
 monkeypatch.setattr(live,'worker_ready',lambda:False)
 data=c.get('/api/v1/live/readiness').json()
 assert not data['placement_ready']
 assert {'BROKER_APPROVAL','RECONCILIATION_WORKER'}<={c['code'] for c in data['blockers']}
 assert c.post('/api/v1/live/orders',headers=h,json=p).status_code==409
 assert Broker.calls==0
