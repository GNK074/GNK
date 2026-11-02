from datetime import timedelta
import pytest
from test_auth import client
from test_multi_user import three,login
from app import main as m
from app.core.config import settings,now
from app.models.trading import BrokerAccount,BrokerCredential,BrokerIntegration
from app.security.encryption import open_credentials
from app.brokers.individual.verifiers import VERIFIERS,VerifiedSession,ValidationError

class Verified:
    identity='MY-DHAN-ACCOUNT'
    def validate(self,c):return VerifiedSession(self.identity,{'access_token':c['access_token']},now()+timedelta(hours=1),'broker_reported')

def body(account='MY-DHAN-ACCOUNT'):
    return {'credentials':{'client_id':account,'access_token':'very-private-broker-token'},'owns_account':True,'terms_accepted':True}

def test_individual_setup_is_available_without_shared_platform_credentials(three,monkeypatch):
    c,_,_=three;login(c,0)
    monkeypatch.setattr(settings,'broker_egress_ip','8.8.8.8')
    catalog=c.get('/api/v1/brokers').json()
    assert len(catalog)==12
    for broker in ('dhan','zerodha','upstox','angelone','fyers','5paisa','icici'):
        item=next(x for x in catalog if x['id']==broker)
        assert item['individual_available'] is True
        assert item['setup_available'] is True and item['supported'] is False
    assert next(x for x in catalog if x['id']=='shoonya')['individual_available'] is False

def test_individual_save_is_encrypted_isolated_and_updates_dashboard(three,monkeypatch):
    c,ids,_=three;h=login(c,0)
    monkeypatch.setitem(VERIFIERS,'dhan',Verified)
    result=c.post('/api/v1/brokers/dhan/individual',json=body(),headers=h)
    assert result.status_code==201,result.text
    assert 'very-private-broker-token' not in result.text
    account=result.json()['id']
    assert c.get('/api/v1/dashboard').json()['connections']==2
    assert c.get('/api/v1/dashboard').json()['mode']=='broker_connected'
    again=c.post('/api/v1/brokers/dhan/individual',json=body(),headers=h)
    assert again.status_code==201 and again.json()['id']==account
    with m.DB() as s:
        credential=s.query(BrokerCredential).filter_by(account_id=account).one()
        assert 'very-private-broker-token' not in credential.ciphertext
        assert open_credentials(ids[0],account,credential.ciphertext)['credentials']['access_token']=='very-private-broker-token'
        assert s.get(BrokerAccount,account).live_authorized is False
    h=login(c,1)
    assert account not in [x['id'] for x in c.get('/api/v1/brokers/connections').json()]
    assert c.post('/api/v1/brokers/dhan/individual',json=body(),headers=h).status_code==409
    assert c.post(f'/api/v1/brokers/dhan/{account}/disconnect',headers=h).status_code==404

def test_identity_mismatch_consent_and_credential_fields_are_rejected(three,monkeypatch):
    c,_,_=three;h=login(c,0);monkeypatch.setitem(VERIFIERS,'dhan',Verified)
    assert c.post('/api/v1/brokers/dhan/individual',json=body('WRONG-ID'),headers=h).status_code==422
    assert c.post('/api/v1/brokers/dhan/individual',json={**body(),'owns_account':False},headers=h).status_code==422
    wrong=body();wrong['credentials']['password']='never-accept-password'
    r=c.post('/api/v1/brokers/dhan/individual',json=wrong,headers=h)
    assert r.status_code==422 and 'never-accept-password' not in r.text
    wrong=body();wrong['credentials']['access_token']='very-private-broker-token\n'
    r=c.post('/api/v1/brokers/dhan/individual',json=wrong,headers=h)
    assert r.status_code==422 and 'very-private-broker-token' not in r.text
    assert not any(a['broker']=='dhan' for a in c.get('/api/v1/brokers/connections').json())

def test_operator_disable_and_failed_provider_never_mark_connected(three,monkeypatch):
    c,_,_=three;h=login(c,0)
    class Failed:
        def validate(self,c):raise ValidationError('Provider authentication failed')
    monkeypatch.setitem(VERIFIERS,'dhan',Failed)
    assert c.post('/api/v1/brokers/dhan/individual',json=body(),headers=h).status_code==422
    with m.DB() as s:s.add(BrokerIntegration(broker='dhan',mode='DISABLED',auth_verified=False));s.commit()
    assert c.post('/api/v1/brokers/dhan/individual',json=body(),headers=h).status_code==409
    assert not c.get('/api/v1/brokers/dhan/setup').json()['individual_available']

def test_unreadable_saved_credentials_are_not_counted_connected(three):
    c,ids,accounts=three;login(c,0)
    with m.DB() as s:
        credential=s.query(BrokerCredential).filter_by(account_id=accounts[0]).one();credential.ciphertext='corrupt-or-unavailable-key';s.commit()
    response=c.get('/api/v1/brokers/connections')
    assert response.status_code==200
    assert response.json()[0]['status']=='reauthorization_required'
    assert c.get('/api/v1/dashboard').json()['connections']==0
