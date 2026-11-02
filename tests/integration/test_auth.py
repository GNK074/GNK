import os
os.environ['JWT_SECRET']='test-secret-for-integration-tests-1234567890'
os.environ['DATABASE_URL']='sqlite://'
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app import main as m
from app.api import auth as auth_routes
from app.services import accounts
import pytest

@pytest.fixture
def client(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    m.Base.metadata.create_all(engine)
    m.DB.configure(bind=engine)
    monkeypatch.setattr(auth_routes,'limit',lambda *args:None)
    from app.security import mfa
    from app.brokers import gateway
    monkeypatch.setattr(mfa,'limit',lambda *args:None)
    monkeypatch.setattr(gateway,'limit',lambda *args:None)
    delivered=[]
    monkeypatch.setattr(accounts,'send_email',lambda email,title,link:delivered.append(link))
    with TestClient(m.app) as c:
        yield c,delivered

def register(c):
    return c.post('/api/v1/auth/register',json={'name':'Test Trader','email':'trader@example.com','password':'StrongPassword!123','terms':True,'privacy':True})

def test_verification_session_csrf_and_revocation(client):
    c,mail=client
    assert register(c).status_code==202
    creds={'email':'trader@example.com','password':'StrongPassword!123'}
    assert c.post('/api/v1/auth/login',json=creds).status_code==403
    token=mail[0].split('token=')[1]
    assert c.post('/api/v1/auth/verify-email',json={'token':token}).status_code==200
    assert c.post('/api/v1/auth/verify-email',json={'token':token}).status_code==400
    r=c.post('/api/v1/auth/login',json=creds)
    assert r.status_code==200
    csrf=r.json()['csrf_token']
    assert 'HttpOnly' in r.headers.get('set-cookie')
    assert c.get('/api/v1/admin/users').status_code==403
    assert c.post('/api/v1/emergency-stop').status_code==403
    assert c.post('/api/v1/broker-connections/initiate',headers={'X-CSRF-Token':csrf}).status_code==409
    assert c.post('/api/v1/auth/refresh',headers={'X-CSRF-Token':csrf}).status_code==200
    csrf=c.get('/api/v1/users/me').json()['csrf_token']
    assert c.post('/api/v1/auth/logout-all',headers={'X-CSRF-Token':csrf}).status_code==200
    assert c.get('/api/v1/users/me').status_code==401

def test_reset_one_time_and_generic_response(client):
    c,mail=client
    register(c)
    a=c.post('/api/v1/auth/forgot-password',json={'email':'trader@example.com'})
    b=c.post('/api/v1/auth/forgot-password',json={'email':'unknown@example.com'})
    assert a.json()==b.json()
    token=mail[-1].split('token=')[1]
    data={'token':token,'password':'AnotherSecure!456'}
    assert c.post('/api/v1/auth/reset-password',json=data).status_code==200
    assert c.post('/api/v1/auth/reset-password',json=data).status_code==400

def test_validation_and_anonymous_access(client):
    c,_=client
    assert c.get('/api/v1/brokers').status_code==401
    assert c.get('/api/v1/dashboard').status_code==401
    assert c.post('/api/v1/auth/register',json={'name':'A','email':'bad','password':'weak','terms':False,'privacy':False}).status_code==422

def test_revocation_after_password_reset(client):
    c,mail=client
    register(c)
    c.post('/api/v1/auth/verify-email',json={'token':mail[0].split('token=')[1]})
    c.post('/api/v1/auth/login',json={'email':'trader@example.com','password':'StrongPassword!123'})
    c.post('/api/v1/auth/forgot-password',json={'email':'trader@example.com'})
    token=mail[-1].split('token=')[1]
    assert c.post('/api/v1/auth/reset-password',json={'token':token,'password':'NewSecurePass!789'}).status_code==200
    assert c.get('/api/v1/users/me').status_code==401

def test_unapproved_brokers_are_never_supported(client):
    c,mail=client
    register(c)
    c.post('/api/v1/auth/verify-email',json={'token':mail[0].split('token=')[1]})
    c.post('/api/v1/auth/login',json={'email':'trader@example.com','password':'StrongPassword!123'})
    data=c.get('/api/v1/brokers').json()
    assert len(data)==12
    assert all(b['supported'] is False for b in data)
    assert c.get('/api/v1/dashboard').json()['live_trading'] is False
