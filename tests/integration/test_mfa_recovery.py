import time
from sqlalchemy import select
from test_auth import client
from test_profile_settings import signed_in
from app import main as m
from app.models.identity import User,MfaRecoveryCode,MfaRecoveryRequest
from app.security import mfa
from app.security.encryption import encrypt


def enroll(c,h):
    secret=c.post('/api/v1/auth/mfa/setup',headers=h).json()['secret']
    r=c.post('/api/v1/auth/mfa/confirm',headers=h,json={'code':mfa.totp(secret,int(time.time()//30))})
    assert r.status_code==200,r.text
    return secret,r.json()['recovery_codes']


def test_backup_email_recovery_revokes_sessions_and_forces_reenrollment(client):
    c,h=signed_in(client)
    secret,codes=enroll(c,h)
    assert len(codes)==len(set(codes))==10
    with m.DB() as s:
        hashes=[x.code_hash for x in s.scalars(select(MfaRecoveryCode))]
        assert all(code not in str(hashes) for code in codes)
    assert c.post('/api/v1/auth/mfa/recovery/request',json={'email':'trader@example.com','password':'StrongPassword!123','recovery_code':codes[0]}).status_code==202
    token=client[1][-1].split('token=')[1]
    # Requesting recovery has not changed MFA yet.
    assert c.get('/api/v1/auth/mfa/status').json()['enabled']
    r=c.post('/api/v1/auth/mfa/recovery/confirm',json={'token':token})
    assert r.status_code==200 and r.json()['completed']
    assert c.post('/api/v1/auth/mfa/recovery/confirm',json={'token':token}).status_code==400
    assert c.get('/api/v1/users/me').status_code==401
    r=c.post('/api/v1/auth/login',json={'email':'trader@example.com','password':'StrongPassword!123'})
    assert r.status_code==200 and r.json()['mfa_required']
    assert c.get('/api/v1/dashboard').status_code==403
    h={'X-CSRF-Token':r.json()['csrf_token']}
    new_secret,new_codes=enroll(c,h)
    assert new_secret!=secret and set(new_codes).isdisjoint(codes)
    assert c.get('/api/v1/users/me').status_code==200


def test_request_is_generic_invalid_code_does_not_send_email_and_pending_requires_review(client):
    c,h=signed_in(client);enroll(c,h)
    count=len(client[1])
    base={'email':'trader@example.com','password':'StrongPassword!123'}
    a=c.post('/api/v1/auth/mfa/recovery/request',json={**base,'recovery_code':'wrong'})
    b=c.post('/api/v1/auth/mfa/recovery/request',json={**base,'email':'missing@example.com'})
    assert a.status_code==b.status_code==202 and a.json()==b.json()
    assert len(client[1])==count
    c.post('/api/v1/auth/mfa/recovery/request',json=base)
    token=client[1][-1].split('token=')[1]
    r=c.post('/api/v1/auth/mfa/recovery/confirm',json={'token':token})
    assert r.status_code==200 and not r.json()['completed']
    assert c.get('/api/v1/auth/mfa/status').json()['enabled']
    assert c.post('/api/v1/auth/mfa/recovery/confirm',json={'token':token}).status_code==400
    assert c.get('/api/v1/admin/mfa-recovery/requests').status_code==403


def test_admin_approval_requires_super_admin_step_up_and_identity_attestation(client,monkeypatch):
    c,h=signed_in(client);enroll(c,h)
    c.post('/api/v1/auth/mfa/recovery/request',json={'email':'trader@example.com','password':'StrongPassword!123'})
    token=client[1][-1].split('token=')[1]
    c.post('/api/v1/auth/mfa/recovery/confirm',json={'token':token})
    secret='GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'
    with m.DB() as s:
        s.add(User(name='Recovery Admin',email='admin@example.com',password=m.hasher.hash('StrongPassword!123'),verified=True,role='SUPER_ADMIN',mfa_enabled=True,mfa_secret=encrypt(secret)));s.commit()
    tick=int(time.time())
    monkeypatch.setattr(mfa.time,'time',lambda:tick)
    r=c.post('/api/v1/auth/login',json={'email':'admin@example.com','password':'StrongPassword!123','totp_code':mfa.totp(secret,tick//30)})
    assert r.status_code==200
    h={'X-CSRF-Token':r.json()['csrf_token']}
    rows=c.get('/api/v1/admin/mfa-recovery/requests').json();assert len(rows)==1
    path='/api/v1/admin/mfa-recovery/requests/'+rows[0]['id']+'/approve'
    tick+=30
    body={'current_password':'StrongPassword!123','code':mfa.totp(secret,tick//30),'identity_verified':True}
    assert c.post(path,headers=h,json={**body,'identity_verified':False}).status_code==422
    assert c.post(path,headers=h,json={**body,'current_password':'wrong'}).status_code==401
    assert c.post(path,headers=h,json=body).status_code==200
    with m.DB() as s:
        target=s.scalar(select(User).where(User.email=='trader@example.com'))
        assert not target.mfa_enabled and target.mfa_reenroll_required


def test_recovery_codes_require_csrf_and_fresh_mfa_and_replace_old_codes(client,monkeypatch):
    c,h=signed_in(client);secret,old=enroll(c,h)
    path='/api/v1/auth/mfa/recovery/codes'
    tick=int(time.time())+30
    monkeypatch.setattr(mfa.time,'time',lambda:tick)
    body={'current_password':'StrongPassword!123','code':mfa.totp(secret,tick//30)}
    assert c.post(path,json=body).status_code==403
    r=c.post(path,headers=h,json=body);assert r.status_code==200
    assert set(r.json()['recovery_codes']).isdisjoint(old)
    assert c.get(path+'/status').json()['remaining']==10
    count=len(client[1])
    c.post('/api/v1/auth/mfa/recovery/request',json={'email':'trader@example.com','password':'StrongPassword!123','recovery_code':old[0]})
    assert len(client[1])==count


def test_invalid_password_and_missing_email_are_generic_and_expired_link_is_rejected(client):
    from datetime import timedelta
    from app.core.config import now
    c,h=signed_in(client);_,codes=enroll(c,h)
    data={'email':'trader@example.com','password':'StrongPassword!123','recovery_code':codes[0]}
    wrong=c.post('/api/v1/auth/mfa/recovery/request',json={**data,'password':'incorrect'})
    absent=c.post('/api/v1/auth/mfa/recovery/request',json={**data,'email':'unknown@example.com'})
    assert wrong.json()==absent.json()
    assert c.post('/api/v1/auth/mfa/recovery/request',json={**data,'user_id':'forged'}).status_code==422
    c.post('/api/v1/auth/mfa/recovery/request',json=data)
    token=client[1][-1].split('token=')[1]
    with m.DB() as s:
        row=s.scalar(select(MfaRecoveryRequest));row.expires=now()-timedelta(seconds=1);s.commit()
    assert c.post('/api/v1/auth/mfa/recovery/confirm',json={'token':token}).status_code==400
    assert c.get('/api/v1/auth/mfa/status').json()['enabled']


def test_password_change_invalidates_pending_recovery(client):
    c,h=signed_in(client);_,codes=enroll(c,h)
    c.post('/api/v1/auth/mfa/recovery/request',json={'email':'trader@example.com','password':'StrongPassword!123','recovery_code':codes[0]})
    token=client[1][-1].split('token=')[1]
    assert c.post('/api/v1/auth/change-password',headers=h,json={'current_password':'StrongPassword!123','password':'NewStrongPassword!456'}).status_code==200
    assert c.post('/api/v1/auth/mfa/recovery/confirm',json={'token':token}).status_code==400


def test_pending_mfa_super_admin_cannot_view_recovery_queue(client,monkeypatch):
    from app.core.config import settings
    c,h=signed_in(client)
    with m.DB() as s:
        user=s.scalar(select(User).where(User.email=='trader@example.com'));user.role='SUPER_ADMIN';s.commit()
    monkeypatch.setattr(settings,'enable_mfa',True)
    r=c.post('/api/v1/auth/login',json={'email':'trader@example.com','password':'StrongPassword!123'})
    assert r.status_code==200 and r.json()['mfa_required']
    assert c.get('/api/v1/admin/mfa-recovery/requests').status_code==403
