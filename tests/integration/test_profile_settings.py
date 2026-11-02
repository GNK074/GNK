import io
from datetime import date, timedelta
from PIL import Image
from sqlalchemy import select
from app import main as m
from app.models.identity import User, LoginSession
from app.security.authentication import hasher
from app.core.config import now
from test_auth import client, register


def signed_in(client):
    c, mail = client
    register(c)
    c.post('/api/v1/auth/verify-email', json={'token': mail[0].split('token=')[1]})
    result = c.post('/api/v1/auth/login', json={'email':'trader@example.com','password':'StrongPassword!123'})
    return c, {'X-CSRF-Token': result.json()['csrf_token']}


def test_profile_validation_and_server_persistence(client):
    c,h = signed_in(client)
    path = '/api/v1/users/me'
    assert c.put(path, json={'name':'Saved Name'}).status_code == 403
    values = {'name':'Saved Name', 'gender':'non_binary','date_of_birth':'1992-05-12','mobile':'+919876543210'}
    assert c.put(path, headers=h, json=values).status_code == 200
    assert all(c.get(path).json()['user'][key] == value for key,value in values.items())
    for invalid in [{'date_of_birth':str(date.today()+timedelta(days=1))},{'mobile':'12345'},{'gender':'invalid'}, {'name':'  '}]:
        assert c.put(path, headers=h, json={**values,**invalid}).status_code == 422
    assert c.put(path+'/preferences', headers=h, json={'theme':'royal_blue'}).status_code == 200
    assert c.get(path).json()['user']['theme'] == 'royal_blue'
    assert c.put(path+'/preferences', headers=h, json={'theme':'evil'}).status_code == 422
    assert 'password' not in c.get(path).json()['user']


def test_private_photo_upload_reset_and_invalid_files(client):
    c,h = signed_in(client)
    path = '/api/v1/users/me/avatar'
    assert c.put(path, headers=h, content=b'<svg/>').status_code == 422
    assert c.put(path, headers=h, content=b'x'*(2*1024*1024+1)).status_code == 413
    image = io.BytesIO()
    Image.new('RGB',(120,80),'purple').save(image,format='JPEG')
    r=c.put(path, headers={**h,'Content-Type':'image/jpeg'}, content=image.getvalue())
    assert r.status_code == 200
    assert r.json()['user']['avatar_url']
    photo=c.get(path)
    assert photo.headers['content-type']=='image/png'
    assert Image.open(io.BytesIO(photo.content)).size == (512,512)
    assert c.delete(path,headers=h).json()['user']['avatar_url'] is None
    assert c.get(path).status_code == 404
    c.post('/api/v1/auth/logout',headers=h)
    assert c.get(path).status_code == 401


def test_session_ownership_and_current_logout(client):
    c,h=signed_in(client)
    with m.DB() as s:
        other=User(email='other@example.com',name='Other User',password=hasher.hash('OtherPassword!123'),verified=True)
        s.add(other);s.flush()
        foreign=LoginSession(user_id=other.id,refresh_hash='a'*64,csrf='b'*64,expires=now()+timedelta(days=1),agent='Other browser')
        own=LoginSession(user_id=s.scalar(select(User.id).where(User.email=='trader@example.com')),refresh_hash='c'*64,csrf='d'*64,expires=now()+timedelta(days=1),agent='Second browser')
        s.add_all([foreign,own]);s.commit(); foreign_id, own_id=foreign.id,own.id
    sessions=c.get('/api/v1/users/me/sessions').json()
    assert foreign_id not in [x['id'] for x in sessions]
    assert sum(x['current'] for x in sessions)==1
    assert c.delete('/api/v1/users/me/sessions/'+foreign_id,headers=h).status_code==404
    assert c.post('/api/v1/auth/logout',headers=h).status_code==200
    with m.DB() as s:
        assert not s.get(LoginSession,own_id).revoked


def test_email_change_verification_and_one_time_link(client):
    c,h=signed_in(client)
    assert c.post('/api/v1/auth/change-email',headers=h,json={'email':'new@example.com','current_password':'wrong'}).status_code==400
    assert c.post('/api/v1/auth/change-email',headers=h,json={'email':'new@example.com','current_password':'StrongPassword!123'}).status_code==202
    assert c.get('/api/v1/users/me').json()['user']['email']=='trader@example.com'
    token=client[1][-1].split('token=')[1]
    assert c.post('/api/v1/auth/confirm-email-change',json={'token':token}).status_code==200
    assert c.post('/api/v1/auth/confirm-email-change',json={'token':token}).status_code==400
    assert c.get('/api/v1/users/me').status_code==401
    assert c.post('/api/v1/auth/login',json={'email':'new@example.com','password':'StrongPassword!123'}).status_code==200


def test_password_change_revokes_sessions_and_invalidates_email_link(client):
    c,h=signed_in(client)
    c.post('/api/v1/auth/change-email',headers=h,json={'email':'new@example.com','current_password':'StrongPassword!123'})
    token=client[1][-1].split('token=')[1]
    r=c.post('/api/v1/auth/change-password',headers=h,json={'current_password':'StrongPassword!123','password':'NewPassword!456'})
    assert r.status_code==200
    assert 'Max-Age=0' in r.headers['set-cookie']
    assert c.get('/api/v1/users/me').status_code==401
    assert c.post('/api/v1/auth/confirm-email-change',json={'token':token}).status_code==400


def test_registration_persists_details_and_rejects_blank_name(client):
    c,mail=client
    fields={'name':'  New Trader  ','email':'new-user@example.com','password':'StrongPassword!123','terms':True,'privacy':True,'gender':'female','date_of_birth':'1990-02-03','mobile':'+447700900123'}
    assert c.post('/api/v1/auth/register',json={**fields,'name':'  '}).status_code==422
    assert c.post('/api/v1/auth/register',json=fields).status_code==202
    with m.DB() as s:
        u=s.scalar(select(User).where(User.email==fields['email']))
        assert u.name=='New Trader' and u.gender=='female'
        assert str(u.date_of_birth)==fields['date_of_birth'] and u.mobile==fields['mobile']


def test_email_confirmation_invalidates_old_recovery_link(client):
    c,h=signed_in(client)
    c.post('/api/v1/auth/forgot-password',json={'email':'trader@example.com'})
    old_reset=client[1][-1].split('token=')[1]
    c.post('/api/v1/auth/change-email',headers=h,json={'email':'new@example.com','current_password':'StrongPassword!123'})
    token=client[1][-1].split('token=')[1]
    assert c.post('/api/v1/auth/confirm-email-change',json={'token':token}).status_code==200
    assert c.post('/api/v1/auth/reset-password',json={'token':old_reset,'password':'Replacement!123'}).status_code==400
