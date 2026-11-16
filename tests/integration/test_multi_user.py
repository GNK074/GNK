import json,time
from datetime import timedelta
from urllib.parse import urlparse,parse_qs
import pytest
from fastapi.testclient import TestClient
from test_auth import client
from app import main as m
from app.core.config import now,digest,settings
from app.models.identity import User
from app.models.trading import BrokerAccount,BrokerCredential,BrokerIntegration,BrokerAuthState,Strategy,Order,Position,ApprovalRequirement
from app.security.encryption import encrypt,seal_credentials,open_credentials
from app.security.mfa import totp
from app.brokers.registry import AUTH_ADAPTERS
from app.brokers.upstox.adapter import BrokerTokens

@pytest.fixture
def three(client):
    c,_=client
    with m.DB() as s:
        ids=[];account_ids=[]
        for i in range(3):
            u=User(name=f'Trader {i}',email=f'user{i}@example.com',password=m.hasher.hash('StrongPassword!123'),verified=True)
            s.add(u);s.flush();a=BrokerAccount(user_id=u.id,broker='upstox',account_identifier=f'account-{i}',status='connected');s.add(a);s.flush()
            s.add(BrokerCredential(user_id=u.id,account_id=a.id,ciphertext=seal_credentials(u.id,a.id,{'access_token':f'private-token-{i}'}),key_version='v1'))
            ids.append(u.id);account_ids.append(a.id)
        s.commit()
    return c,ids,account_ids

def login(c,i):
    response=c.post('/api/v1/auth/login',json={'email':f'user{i}@example.com','password':'StrongPassword!123'})
    assert response.status_code==200,response.text
    headers = {'X-CSRF-Token':response.json()['csrf_token']}
    if response.json().get('mfa_required'):
        return headers
    document = c.get('/api/v1/compliance/disclosure').json()
    result = c.post('/api/v1/compliance/disclosure/acknowledge', headers=headers, json={'disclosure_id':document['id'], 'disclosure_version':document['version'], 'content_sha256':document['content_sha256'], 'acknowledged':True})
    assert result.status_code == 200, result.text
    return headers


def test_approval_requires_evidence_and_rechecks_all_18(three):
    c,ids,_=three
    with m.DB() as s:s.get(User,ids[0]).role='SUPER_ADMIN';s.commit()
    h=login(c,0)
    assert c.post('/api/v1/admin/brokers/upstox/approval',headers=h).status_code==200
    evidence={'reference':'evidence://security/test-run','sha256':'a'*64,'expires_at':(now()+timedelta(days=1)).isoformat()}
    for n in range(1,19):
        result=c.post(f'/api/v1/admin/brokers/upstox/requirements/{n}/verify',json=evidence,headers=h)
        assert result.status_code==200,result.text
    response=c.post('/api/v1/admin/brokers/upstox/production-approval',json={'completed_count':999},headers=h)
    assert response.status_code==409
    assert response.json()['detail']['missing_requirements']==[]
    assert 'runtime_blocker' in response.json()['detail']
    with m.DB() as s:
        row=s.query(ApprovalRequirement).filter_by(broker='upstox',requirement=8).one();row.passed=False;s.commit()
    response=c.post('/api/v1/admin/brokers/upstox/production-approval',headers=h)
    assert 8 in response.json()['detail']['missing_requirements']
    assert c.get('/api/v1/admin/brokers/upstox/production-status').json()['approved'] is False

class FakeAdapter:
    calls=0
    def __init__(self,*args):pass
    def authorization_url(self,state):return 'https://api.upstox.com/authorize?state='+state
    def exchange(self,code):
        type(self).calls+=1
        return BrokerTokens('secret-broker-access','real-customer-'+code)


def test_mfa_enrollment_and_code_replay(three,monkeypatch):
    c,_,_=three
    monkeypatch.setattr(settings,'enable_mfa',True)
    h=login(c,0)
    assert c.get('/api/v1/orders').status_code==403
    setup=c.post('/api/v1/auth/mfa/setup',headers=h);assert setup.status_code==200
    secret=setup.json()['secret'];code=totp(secret,int(time.time()//30))
    assert c.post('/api/v1/auth/mfa/confirm',json={'code':code},headers=h).status_code==200
    assert c.get('/api/v1/orders').status_code==200
    assert c.post('/api/v1/auth/login',json={'email':'user0@example.com','password':'StrongPassword!123','totp_code':code}).status_code==401

def test_each_users_risk_settings_are_independent(three):
    c,_,_=three
    for i in range(3):
        h=login(c,i)
        value={'max_quantity':i+1,'max_order_value':'1000','max_daily_orders':10,'max_daily_loss':'100','max_positions':2}
        assert c.put('/api/v1/risk/configuration',json=value,headers=h).status_code==200
        assert c.put('/api/v1/risk/configuration',json={**value,'user_id':'other-owner'},headers=h).status_code==422
    for i in range(3):
        login(c,i)
        assert c.get('/api/v1/risk/configuration').json()['max_quantity']==i+1
