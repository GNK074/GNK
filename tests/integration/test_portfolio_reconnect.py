"""Verified connections queue fresh reads; obsolete syncs cannot undo recovery."""
from test_auth import client
from test_multi_user import three,login
from test_portfolio import portfolio,put,holding,FixtureAdapter
from app import main as m
from app.core.config import now
from app.portfolio import service as svc
from app.portfolio.models import PortfolioSync,PortfolioSnapshot
from app.portfolio.adapters import PortfolioError
from app.models.trading import BrokerAccount,BrokerCredential
from app.brokers.individual.verifiers import VERIFIERS,VerifiedSession
from app.security.encryption import seal_credentials
from sqlalchemy import select,func
from datetime import timedelta
import pytest

def test_connect_queues_first_sync_atomically(three,monkeypatch):
 c,ids,aids=three;h=login(c,0)
 class Verified:
  def validate(self,data):return VerifiedSession('new-dhan',{'access_token':data['access_token']},now()+timedelta(hours=2),'broker_reported')
 monkeypatch.setitem(VERIFIERS,'dhan',Verified)
 result=c.post('/api/v1/brokers/dhan/individual',headers=h,json={'credentials':{'client_id':'new-dhan','access_token':'fixture-only'},'owns_account':True,'terms_accepted':True})
 assert result.status_code==201,result.text
 with m.DB() as s:
  state=s.scalar(select(PortfolioSync).where(PortfolioSync.account_id==result.json()['id']))
  assert state and state.state=='QUEUED' and state.errors=={} and svc.utc(state.next_attempt_at)<=now()

def test_reconnect_clears_old_error_backoff_and_worker_syncs_new_token(portfolio,monkeypatch):
 c,ids,aids=portfolio;h=login(c,0);put(ids[0],aids[0],'holdings',holding())
 with m.DB() as s:
  s.get(BrokerAccount,aids[0]).broker='dhan'
  s.add(PortfolioSync(user_id=ids[0],account_id=aids[0],state='SESSION_EXPIRED',errors={'session':'SESSION_EXPIRED'},failures=4,next_attempt_at=now()+timedelta(minutes=15)));s.commit()
 class Verified:
  def validate(self,data):return VerifiedSession('account-0',{'access_token':data['access_token']},now()+timedelta(hours=2),'broker_reported')
 monkeypatch.setitem(VERIFIERS,'dhan',Verified)
 result=c.post('/api/v1/brokers/dhan/individual',headers=h,json={'credentials':{'client_id':'account-0','access_token':'replacement-fixture'},'owns_account':True,'terms_accepted':True})
 assert result.status_code==201,result.text
 with m.DB() as s:
  state=s.scalar(select(PortfolioSync));assert state.state=='QUEUED' and state.errors=={} and state.failures==0
  assert s.scalar(select(func.count()).select_from(PortfolioSnapshot))==1 # preserve old data, never relabel it fresh
 account=c.get('/api/v1/dhan/status').json()['accounts'][0]
 assert account['connection_status']=='connected' and account['status']=='PENDING' and account['errors']=={}
 FixtureAdapter.error_kind=None;monkeypatch.setattr(svc,'build_adapter',lambda *a:FixtureAdapter())
 assert svc.sync_account(ids[0],aids[0])
 account=c.get('/api/v1/dhan/status').json()['accounts'][0]
 assert account['status']=='CONNECTED' and account['last_success'] and account['completed_at']
 with m.DB() as s:
  assert s.scalar(select(func.count()).select_from(PortfolioSnapshot))==5
  assert s.get(BrokerAccount,aids[0]).kill_switch and not s.get(BrokerAccount,aids[0]).live_authorized

def replace(s,uid,aid):
 credential=s.scalar(select(BrokerCredential).where(BrokerCredential.account_id==aid))
 credential.ciphertext=seal_credentials(uid,aid,{'credentials':{'access_token':'new-fixture'}})
 svc.connected(s,uid,aid,'upstox');s.commit()

def test_expired_old_request_cannot_overwrite_new_connection_queue(portfolio,monkeypatch):
 c,ids,aids=portfolio
 class Reconnected:
  def fetch(self,kind):
   with m.DB() as s:replace(s,ids[0],aids[0])
   raise PortfolioError('SESSION_EXPIRED')
 monkeypatch.setattr(svc,'build_adapter',lambda *a:Reconnected())
 assert svc.sync_account(ids[0],aids[0]) is False
 with m.DB() as s:
  state=s.scalar(select(PortfolioSync));assert state.state=='QUEUED' and state.errors=={} and state.failures==0

def test_unexpected_old_failure_cannot_overwrite_reconnect(portfolio,monkeypatch):
 c,ids,aids=portfolio;FixtureAdapter.error_kind=None
 monkeypatch.setattr(svc,'build_adapter',lambda *a:FixtureAdapter())
 def fail(*args):
  with m.DB() as s:replace(s,ids[0],aids[0])
  raise RuntimeError('private-fixture-never-log')
 monkeypatch.setattr(svc,'classify_holdings',fail)
 with pytest.raises(RuntimeError):svc.sync_account(ids[0],aids[0])
 with m.DB() as s:
  state=s.scalar(select(PortfolioSync));assert state.state=='QUEUED' and state.errors=={} and state.failures==0

def test_endpoint_failures_are_visible_and_keep_backoff(portfolio,monkeypatch,capsys):
 c,ids,aids=portfolio
 class Denied:
  def fetch(self,kind):raise PortfolioError('PERMISSION_DENIED')
 monkeypatch.setattr(svc,'build_adapter',lambda *a:Denied())
 assert svc.sync_account(ids[0],aids[0])
 assert 'Codes:' in capsys.readouterr().out
 h=login(c,0)
 account=c.get('/api/v1/portfolio/accounts').json()['items'][0]
 assert account['status']=='ERROR' and account['errors']['holdings']=='PERMISSION_DENIED' and account['next_attempt_at']
 c.post('/api/v1/portfolio/refresh',headers=h,json={'account_id':aids[0]})
 with m.DB() as s:assert svc.utc(s.scalar(select(PortfolioSync)).next_attempt_at)>now()
