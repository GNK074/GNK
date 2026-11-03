"""Logout must revoke sessions after access expiry without weakening CSRF/MFA."""
from datetime import timedelta
import jwt,pytest
from sqlalchemy import select
from test_auth import client
from test_profile_settings import signed_in
from app import main as m
from app.core.config import SECRET,now,digest,settings
from app.models.identity import LoginSession,User

def replace_cookie(c,name,value):
    for cookie in list(c.cookies.jar):
        if cookie.name==name:c.cookies.delete(name,domain=cookie.domain,path=cookie.path)
    if value is not None:c.cookies.set(name,value,domain='testserver.local',path='/api/v1')

def current_session(c):
    with m.DB() as s:
        return s.scalar(select(LoginSession).where(LoginSession.refresh_hash==digest(c.cookies.get('refresh')))).id

def expire_access(c):
    claims=jwt.decode(c.cookies.get('access'),SECRET,algorithms=['HS256'],audience='gnk-web',issuer='gnk-api')
    claims['exp']=now()-timedelta(minutes=1)
    replace_cookie(c,'access',jwt.encode(claims,SECRET,algorithm='HS256'))

def test_current_logout_after_access_expiry(client):
    c,h=signed_in(client);sid=current_session(c);expire_access(c)
    assert c.get('/api/v1/users/me').status_code==401
    bootstrap=c.get('/api/v1/auth/session');assert bootstrap.status_code==200
    assert set(bootstrap.json())=={'csrf_token'}
    assert c.get('/api/v1/users/me').status_code==401 # bootstrap grants no access
    r=c.post('/api/v1/auth/logout',headers={'X-CSRF-Token':bootstrap.json()['csrf_token']})
    assert r.status_code==200 and r.json()['all_devices'] is False
    assert c.cookies.get('access') is None and c.cookies.get('refresh') is None
    assert all('Path=/api/v1' in value and 'HttpOnly' in value and 'SameSite=strict' in value for value in r.headers.get_list('set-cookie'))
    with m.DB() as s:assert s.get(LoginSession,sid).revoked

def test_all_devices_after_expiry_revokes_only_owner(client):
    c,h=signed_in(client);sid=current_session(c)
    with m.DB() as s:
        first=s.get(LoginSession,sid)
        own=LoginSession(user_id=first.user_id,refresh_hash='a'*64,csrf='b'*64,expires=now()+timedelta(days=1),agent='second device');s.add(own)
        other=User(name='Other user',email='other@example.com',password='unused',verified=True);s.add(other);s.flush()
        foreign=LoginSession(user_id=other.id,refresh_hash='c'*64,csrf='d'*64,expires=now()+timedelta(days=1),agent='other user');s.add(foreign);s.commit();own_id,foreign_id=own.id,foreign.id
    expire_access(c)
    proof=c.get('/api/v1/auth/session').json()['csrf_token']
    r=c.post('/api/v1/auth/logout-all',headers={'X-CSRF-Token':proof});assert r.status_code==200 and r.json()['all_devices']
    with m.DB() as s:
        assert s.get(LoginSession,sid).revoked and s.get(LoginSession,own_id).revoked
        assert not s.get(LoginSession,foreign_id).revoked

def test_logout_during_mfa_enrollment_does_not_unlock_workspace(client):
    c,h=signed_in(client);sid=current_session(c)
    with m.DB() as s:s.get(LoginSession,sid).mfa_complete=False;s.commit()
    assert c.get('/api/v1/users/me').status_code==403
    proof=c.get('/api/v1/auth/session').json()['csrf_token']
    assert c.get('/api/v1/users/me').status_code==403
    assert c.post('/api/v1/auth/logout',headers={'X-CSRF-Token':proof}).status_code==200
    with m.DB() as s:assert s.get(LoginSession,sid).revoked

def test_csrf_and_cross_origin_requests_cannot_revoke(client):
    c,h=signed_in(client);sid=current_session(c)
    for path in ('/api/v1/auth/logout','/api/v1/auth/logout-all'):
        assert c.post(path).status_code==403
        assert c.post(path,headers={'X-CSRF-Token':'wrong'}).status_code==403
        assert c.post(path,headers={**h,'Origin':'https://evil.example'}).status_code==403
        assert c.post(path,headers={**h,'Sec-Fetch-Site':'cross-site'}).status_code==403
    assert c.get('/api/v1/auth/session',headers={'Origin':'https://evil.example'}).status_code==403
    with m.DB() as s:assert not s.get(LoginSession,sid).revoked

def test_csrf_rotation_can_be_recovered_without_refresh(client):
    c,h=signed_in(client);sid=current_session(c)
    with m.DB() as s:s.get(LoginSession,sid).csrf='new-proof-from-other-tab';s.commit()
    assert c.post('/api/v1/auth/logout',headers=h).status_code==403
    proof=c.get('/api/v1/auth/session').json()['csrf_token'];assert proof=='new-proof-from-other-tab'
    assert c.post('/api/v1/auth/logout',headers={'X-CSRF-Token':proof}).status_code==200

def test_expired_session_local_cleanup_is_idempotent_but_all_devices_requires_identity(client):
    c,h=signed_in(client);sid=current_session(c)
    with m.DB() as s:s.get(LoginSession,sid).expires=now()-timedelta(seconds=1);s.commit()
    assert c.get('/api/v1/auth/session').status_code==401
    assert c.post('/api/v1/auth/logout-all',headers=h).status_code==401
    assert c.post('/api/v1/auth/logout',headers=h).status_code==200
    assert c.post('/api/v1/auth/logout').status_code==200
    assert c.cookies.get('access') is None and c.cookies.get('refresh') is None

def test_logout_with_only_valid_access_cookie(client):
    c,h=signed_in(client);sid=current_session(c);replace_cookie(c,'refresh',None)
    assert c.get('/api/v1/auth/session').status_code==200
    assert c.post('/api/v1/auth/logout',headers=h).status_code==200
    with m.DB() as s:assert s.get(LoginSession,sid).revoked


def test_same_origin_www_host_can_logout_with_csrf(client):
    c,h=signed_in(client)
    # The browser cookies belong to testserver; simulate a reverse proxy's Host
    # on that authenticated request without copying credentials to another site.
    headers={**h,'Host':'www.gnkalgo.com','Origin':'https://www.gnkalgo.com','Sec-Fetch-Site':'same-origin'}
    assert c.post('/api/v1/auth/logout',headers=headers).status_code==200


def test_logout_keeps_live_execution_configuration_unchanged(client,monkeypatch):
    c,h=signed_in(client)
    monkeypatch.setattr(settings,'trading_enabled',True)
    monkeypatch.setattr(settings,'live_trading_enabled',True)
    monkeypatch.setattr(settings,'upstox_execution_enabled',True)
    assert c.post('/api/v1/auth/logout-all',headers=h).status_code==200
    assert settings.trading_enabled and settings.live_trading_enabled and settings.upstox_execution_enabled
