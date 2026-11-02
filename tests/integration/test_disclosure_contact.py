from datetime import timedelta
from sqlalchemy import select, func
from test_auth import client
from test_profile_settings import signed_in
from app import main as m
from app.core.config import settings, now
from app.compliance.models import DisclosureAcknowledgment
from app.compliance import service
from app.api.public import SERVICES, QUICK_LINKS


def acknowledge(c, headers, **overrides):
    d=c.get('/api/v1/compliance/disclosure').json()
    return c.post('/api/v1/compliance/disclosure/acknowledge',headers=headers,json={'disclosure_id':d['id'],'disclosure_version':d['version'],'content_sha256':d['content_sha256'],'acknowledged':True,**overrides})


def test_auth_csrf_server_enforcement_and_idempotency(client):
    c=client[0]
    assert c.get('/api/v1/compliance/disclosure').status_code==401
    c,h=signed_in(client)
    assert c.get('/api/v1/compliance/disclosure/status').json()['required']
    sid=c.post('/api/v1/strategies',headers=h,json={'name':'Disclosure test'}).json()['id']
    order={'strategy_id':sid,'symbol':'TEST','side':'BUY','quantity':1,'price':'100','idempotency_key':'disclosure-order-001'}
    assert c.post('/api/v1/paper/orders',headers=h,json=order).status_code==428
    assert c.post('/api/v1/live/orders',headers=h,json={**order,'broker_account_id':'missing-broker'}).status_code==428
    assert acknowledge(c,{}).status_code==403
    assert acknowledge(c,h,user_id='another-user').status_code==422
    assert acknowledge(c,h,acknowledged=False).status_code==422
    assert acknowledge(c,h).status_code==200
    assert acknowledge(c,h).status_code==200
    assert not c.get('/api/v1/compliance/disclosure/status').json()['required']
    assert c.post('/api/v1/paper/orders',headers=h,json=order).status_code==201
    with m.DB() as s:
        items=s.scalars(select(DisclosureAcknowledgment)).all()
        assert len(items)==1 and items[0].acknowledged_at and items[0].user_id


def test_new_login_version_and_time_window_require_fresh_receipts(client,monkeypatch):
    c,h=signed_in(client)
    assert acknowledge(c,h).status_code==200
    r=c.post('/api/v1/auth/login',json={'email':'trader@example.com','password':'StrongPassword!123'})
    h={'X-CSRF-Token':r.json()['csrf_token']}
    assert c.get('/api/v1/compliance/disclosure/status').json()['required']
    old=c.get('/api/v1/compliance/disclosure').json()
    assert acknowledge(c,h).status_code==200
    monkeypatch.setattr(settings,'disclosure_version','new-approved-release')
    assert c.get('/api/v1/compliance/disclosure/status').json()['required']
    assert acknowledge(c,h,disclosure_version=old['version']).status_code==409
    assert acknowledge(c,h).status_code==200
    monkeypatch.setattr(service,'now',lambda:now()+timedelta(days=2))
    assert c.get('/api/v1/compliance/disclosure/status').json()['required']


def test_content_change_invalidates_receipt_and_exact_requested_text(client,monkeypatch):
    from app.compliance.content import CONTENT
    c,h=signed_in(client)
    doc=c.get('/api/v1/compliance/disclosure').json()
    assert '₹50,000' in doc['points'][1]
    assert 'January 25, 2023' in doc['source'] and 'FY 2021-22' in doc['source']
    assert acknowledge(c,h).status_code==200
    monkeypatch.setitem(CONTENT,'historical_note','Revised approved note')
    assert c.get('/api/v1/compliance/disclosure/status').json()['required']


def test_user_receipts_are_isolated(client):
    from app.models.identity import User
    c,h=signed_in(client)
    assert acknowledge(c,h).status_code==200
    with m.DB() as s:
        s.add(User(name='Second Trader',email='second@example.com',verified=True,password=m.hasher.hash('StrongPassword!123')));s.commit()
    r=c.post('/api/v1/auth/login',json={'email':'second@example.com','password':'StrongPassword!123'})
    h={'X-CSRF-Token':r.json()['csrf_token']}
    assert c.get('/api/v1/compliance/disclosure/status').json()['required']
    assert acknowledge(c,h).status_code==200
    with m.DB() as s:
        assert s.scalar(select(func.count()).select_from(DisclosureAcknowledgment))==2


def test_public_contact_hides_unverified_claims_channels_and_maps(client,monkeypatch):
    monkeypatch.setattr(settings,'company_registration_verified',False)
    monkeypatch.setattr(settings,'contact_channels_verified',False)
    monkeypatch.setattr(settings,'company_office_address_verified',False)
    d=client[0].get('/api/v1/public/contact').json()
    assert not d['company']['registration_verified'] and not d['company']['sebi_registration']
    assert 'SEBI registered' not in d['company']['description']
    assert d['regulatory_notice'] is None
    assert d['phones']==[] and d['emails']==[] and d['socials']==[] and d['maps_address'] is None
    assert [(x['label'],x['href']) for x in d['services']]==SERVICES
    assert [(x['label'],x['href']) for x in d['quick_links']]==QUICK_LINKS


def test_verified_contact_links_and_regulatory_notice(client,monkeypatch):
    for key,value in {'contact_channels_verified':True,'company_registration_verified':True,'company_legal_name':'Test Legal Entity','company_sebi_registration':'INH000000001','company_basl_applicable':True,'company_basl_membership':'TEST-MEMBER','company_office_address_verified':True,'company_office_address':'Test building, Bengaluru 560049'}.items():
        monkeypatch.setattr(settings,key,value)
    d=client[0].get('/api/v1/public/contact').json()
    assert d['phones'][0]['href']=='tel:+918297200073'
    assert d['phones'][1]['href']=='tel:+918297200074'
    assert d['emails']==['info@gnkalgo.com','gnkalgo.admin@gmail.com']
    assert len(d['socials'])==5 and d['maps_address']
    assert d['regulatory_notice'] and d['company']['name']=='Test Legal Entity'


def test_refresh_rotation_keeps_acknowledgment_for_same_login(client):
    c,h=signed_in(client)
    assert acknowledge(c,h).status_code==200
    assert c.post('/api/v1/auth/refresh',headers=h).status_code==200
    assert not c.get('/api/v1/compliance/disclosure/status').json()['required']
