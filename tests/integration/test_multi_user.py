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

def strategy(c,headers):
    r=c.post('/api/v1/strategies',json={'name':'Paper research'},headers=headers)
    assert r.status_code==201,r.text
    return r.json()['id']

def payload(sid,key='unique-order-0001'):
    return {'strategy_id':sid,'symbol':'NIFTYTEST','side':'BUY','quantity':2,'price':'100.0000','idempotency_key':key}

def test_three_users_cannot_access_each_others_records(three):
    c,ids,accounts=three;records=[]
    for i in range(3):
        h=login(c,i);sid=strategy(c,h)
        r=c.post('/api/v1/paper/orders',json=payload(sid),headers=h);assert r.status_code==201,r.text
        records.append((sid,r.json()['id'],c.get('/api/v1/positions').json()[0]['id']))
    for i in range(3):
        h=login(c,i)
        assert len(c.get('/api/v1/orders').json())==1
        assert len(c.get('/api/v1/positions').json())==1
        for j in range(3):
            if i==j:continue
            sid,oid,pid=records[j]
            assert c.get('/api/v1/orders/'+oid).status_code==404
            assert c.get('/api/v1/positions/'+pid).status_code==404
            assert c.put('/api/v1/strategies/'+sid,json={'name':'Stolen'},headers=h).status_code==404
            assert c.post('/api/v1/paper/orders',json=payload(sid,'cross-user-key'),headers=h).status_code==404
            assert c.post(f'/api/v1/brokers/upstox/{accounts[j]}/disconnect',headers=h).status_code==404
        assert c.post('/api/v1/live/orders',json={**payload(records[i][0],'cross-live-key'),'broker_account_id':accounts[(i+1)%3]},headers=h).status_code==404
        assert c.get('/api/v1/admin/users').status_code==403
        assert c.post('/api/v1/strategies',json={'name':'Escalate','user_id':ids[(i+1)%3],'approved':True},headers=h).status_code==422
        own=c.get('/api/v1/brokers/connections').json();assert len(own)==1
        assert 'private-token' not in json.dumps(own)
    with m.DB() as s:
        creds=s.query(BrokerCredential).all()
        assert all('private-token' not in x.ciphertext for x in creds)
        with pytest.raises(ValueError):open_credentials(ids[0],accounts[0],creds[1].ciphertext)

def test_paper_idempotency_risk_and_emergency_stops(three):
    c,_,accounts=three;h=login(c,0);sid=strategy(c,h);data=payload(sid)
    a=c.post('/api/v1/paper/orders',json=data,headers=h);b=c.post('/api/v1/paper/orders',json=data,headers=h)
    assert a.json()['id']==b.json()['id']
    assert c.post('/api/v1/paper/orders',json={**data,'quantity':3},headers=h).status_code==409
    assert c.post('/api/v1/paper/orders',json={**data,'quantity':101,'idempotency_key':'over-limit-0001'},headers=h).status_code==422
    assert c.post('/api/v1/emergency-stop',headers=h).status_code==200
    assert c.post('/api/v1/paper/orders',json={**data,'idempotency_key':'stopped-order-01'},headers=h).status_code==409
    h1=login(c,1);sid1=strategy(c,h1)
    assert c.post('/api/v1/paper/orders',json=payload(sid1),headers=h1).status_code==201
    assert c.post('/api/v1/live/orders',json={**payload(sid1,'live-blocked-01'),'broker_account_id':accounts[1]},headers=h1).status_code==409

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

@pytest.fixture
def configured(three,monkeypatch):
    c,ids,accounts=three
    with m.DB() as s:
        s.add(BrokerIntegration(broker='upstox',mode='HYBRID',auth_verified=True,client_id='app-key',encrypted_client_secret=encrypt('app-secret'),redirect_uri='https://api.gnkalgo.com/api/v1/brokers/upstox/callback'));s.commit()
    monkeypatch.setitem(AUTH_ADAPTERS,'upstox',FakeAdapter);FakeAdapter.calls=0
    return three

def start_auth(c,h):
    r=c.post('/api/v1/brokers/upstox/connect',json={'mode':'PLATFORM'},headers=h)
    assert r.status_code==200,r.text
    return parse_qs(urlparse(r.json()['authorization_url']).query)['state'][0],r.json()['account_id']

def test_callback_is_single_use_and_ignores_browser_user_id(configured):
    c,ids,_=configured;h=login(c,0);state,account=start_auth(c,h)
    h=login(c,1)
    response=c.get('/api/v1/brokers/upstox/callback',params={'state':state,'code':'new-account','user_id':ids[1]},follow_redirects=False)
    assert response.status_code==303
    assert 'secret-broker-access' not in response.text
    assert c.get('/api/v1/brokers/upstox/callback',params={'state':state,'code':'new-account'},follow_redirects=False).status_code==400
    assert FakeAdapter.calls==1
    with m.DB() as s:
        a=s.get(BrokerAccount,account);assert a.user_id==ids[0] and a.status=='connected'
        cred=s.query(BrokerCredential).filter_by(account_id=account).one()
        assert open_credentials(ids[0],account,cred.ciphertext)['access_token']=='secret-broker-access'

def test_expired_wrong_state_and_token_exchange_failure(configured,monkeypatch):
    c,_,_=configured;h=login(c,0);state,account=start_auth(c,h)
    assert c.get('/api/v1/brokers/upstox/callback',params={'state':'incorrect','code':'x'}).status_code==400
    with m.DB() as s:
        row=s.query(BrokerAuthState).filter_by(state_hash=digest(state)).one();row.expires_at=now()-timedelta(seconds=1);s.commit()
    assert c.get('/api/v1/brokers/upstox/callback',params={'state':state,'code':'x'}).status_code==400
    state,account=start_auth(c,h)
    def failed(*args):raise ValueError('provider-secret-never-expose')
    monkeypatch.setattr(FakeAdapter,'exchange',failed)
    response=c.get('/api/v1/brokers/upstox/callback',params={'state':state,'code':'x'},follow_redirects=False)
    assert response.status_code==303 and 'result=failed' in response.headers['location']
    assert 'provider-secret' not in response.text
    assert c.get('/api/v1/brokers/upstox/callback',params={'state':state,'code':'x'}).status_code==400

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

def test_realized_daily_loss_blocks_further_paper_orders(three):
    c,_,_=three;h=login(c,0);sid=strategy(c,h)
    risk={'max_quantity':100,'max_order_value':'100000','max_daily_orders':50,'max_daily_loss':'10','max_positions':3}
    assert c.put('/api/v1/risk/configuration',json=risk,headers=h).status_code==200
    assert c.post('/api/v1/paper/orders',json=payload(sid,'buy-loss-test'),headers=h).status_code==201
    sell={**payload(sid,'sell-loss-test'),'side':'SELL','price':'90.0000'}
    assert c.post('/api/v1/paper/orders',json=sell,headers=h).status_code==201
    assert c.get('/api/v1/positions').json()[0]['realized_pnl']=='-20.0000'
    assert c.post('/api/v1/paper/orders',json=payload(sid,'blocked-after-loss'),headers=h).status_code==422

def test_disconnect_alias_checks_owner_and_removes_local_credentials(three):
    c,ids,accounts=three;h=login(c,0)
    assert c.post('/api/v1/brokers/upstox/disconnect',json={'account_id':accounts[1]},headers=h).status_code==404
    assert c.post('/api/v1/brokers/upstox/disconnect',json={'account_id':accounts[0]},headers=h).status_code==200
    with m.DB() as s:
        assert s.query(BrokerCredential).filter_by(account_id=accounts[0]).count()==0
        assert s.get(BrokerAccount,accounts[0]).status=='disconnected'
        assert s.get(BrokerAccount,accounts[1]).status=='connected'

def test_reauthorization_reuses_only_the_same_owners_broker_identity(configured):
    c,ids,_=configured;h=login(c,0)
    state,first=start_auth(c,h)
    assert c.get('/api/v1/brokers/upstox/callback',params={'state':state,'code':'same-identity'},follow_redirects=False).status_code==303
    state,second=start_auth(c,h)
    response=c.get('/api/v1/brokers/upstox/callback',params={'state':state,'code':'same-identity'},follow_redirects=False)
    assert 'result=connected' in response.headers['location']
    with m.DB() as s:
        assert s.get(BrokerAccount,first).status=='connected'
        assert s.get(BrokerAccount,second).status=='superseded'
        assert s.query(BrokerCredential).filter_by(account_id=first).count()==1
    h=login(c,1);state,foreign=start_auth(c,h)
    response=c.get('/api/v1/brokers/upstox/callback',params={'state':state,'code':'same-identity'},follow_redirects=False)
    assert 'result=failed' in response.headers['location']
    with m.DB() as s:
        assert s.get(BrokerAccount,first).user_id==ids[0]
        assert s.get(BrokerAccount,foreign).status=='failed'
