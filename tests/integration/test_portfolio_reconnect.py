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
