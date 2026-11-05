from datetime import timedelta
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import now, settings, digest, expired
from app.database.session import db
from app.models.identity import User
from app.models.trading import BrokerIntegration, BrokerAccount, BrokerCredential, BrokerAuthState
from app.security.authentication import auth, limit
from app.security.encryption import encrypt, decrypt, seal_credentials
from app.security.ownership import owned
from app.services.accounts import audit
from .registry import AUTH_ADAPTERS, BROKER_IDS
router = APIRouter(prefix='/api/v1/brokers')

class ConnectInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: str = Field(default='PLATFORM', pattern='^(PLATFORM|INDIVIDUAL)$')
    client_id: str = Field(default='', max_length=200)
    client_secret: str = Field(default='', max_length=1000)

def integration(s, broker):
    config = s.get(BrokerIntegration, broker)
    if broker not in AUTH_ADAPTERS or not config or (not config.auth_verified) or (config.mode == 'DISABLED'):
        raise HTTPException(409, 'Broker authentication requires operator verification and approval; integration disabled')
    return config

def account_public(a):
    return dict(id=a.id, broker=a.broker, account_identifier='***' + a.account_identifier[-4:] if a.account_identifier else None, status=a.status, live_authorized=a.live_authorized, kill_switch=a.kill_switch)

@router.get('/connections')
def connections(u=Depends(auth), s: Session=Depends(db)):
    output = []
    for a in s.scalars(select(BrokerAccount).where(BrokerAccount.user_id == u.id, BrokerAccount.status != 'superseded')):
        value = account_public(a)
        credential = s.scalar(select(BrokerCredential).where(BrokerCredential.user_id == u.id, BrokerCredential.account_id == a.id))
        value['expires_at'] = credential.expires_at if credential else None
        if credential:
            from app.security.encryption import open_credentials
            try:
                payload=open_credentials(u.id,a.id,credential.ciphertext)
                value['verified_at']=payload.get('verified_at')
                value['expiry_basis']=payload.get('expiry_basis')
                value['connection_method']=payload.get('connection_method','broker_authorization')
            except Exception:
                value['status']='reauthorization_required'
                value['connection_issue']='Saved session cannot be opened; reconnect this account.'
        elif a.status=='connected':
            value['status']='reauthorization_required'
        if a.status == 'connected' and credential and credential.expires_at and expired(credential.expires_at):
            value['status'] = 'expired'
        output.append(value)
    return output

@router.post('/{broker}/connect')
@router.post('/{broker}/reauthorize')
def connect(broker: str, data: ConnectInput, request: Request, u=Depends(auth), s: Session=Depends(db)):
    limit(request, 'broker-connect', u.id)
    config = integration(s, broker)
    if config.mode not in (data.mode, 'HYBRID'):
        raise HTTPException(409, 'Requested credential mode is not approved')
    if data.mode == 'INDIVIDUAL':
        if not data.client_id or not data.client_secret:
            raise HTTPException(422, 'Individual API application credentials are required')
        cid = data.client_id
        secret = data.client_secret
    else:
        if not config.client_id or not config.encrypted_client_secret:
            raise HTTPException(409, 'Platform application configuration incomplete')
        cid = config.client_id
        secret = decrypt(config.encrypted_client_secret)
    s.scalar(select(User).where(User.id == u.id).with_for_update())
    account = BrokerAccount(user_id=u.id, broker=broker)
    s.add(account)
    s.flush()
    raw = secrets.token_urlsafe(48)
    state = BrokerAuthState(user_id=u.id, account_id=account.id, broker=broker, state_hash=digest(raw), expires_at=now() + timedelta(seconds=settings.broker_callback_state_ttl_seconds))
    s.add(state)
    s.add(BrokerCredential(user_id=u.id, account_id=account.id, ciphertext=seal_credentials(u.id, account.id, dict(client_id=cid, client_secret=secret)), key_version=settings.encryption_key_version))
    audit(s, u.id, 'broker_auth_started:' + broker)
    s.commit()
    adapter = AUTH_ADAPTERS[broker](cid, secret, config.redirect_uri)
    return {'authorization_url': adapter.authorization_url(raw), 'account_id': account.id}

@router.get('/{broker}/callback')
def callback(broker: str, request: Request, state: str='', code: str='', s: Session=Depends(db)):
    from app.database.tenancy import set_context
    set_context(s, callback_hash=digest(state))
    row = s.scalar(select(BrokerAuthState).where(BrokerAuthState.state_hash == digest(state), BrokerAuthState.broker == broker))
    if not row or expired(row.expires_at) or row.consumed:
        raise HTTPException(400, 'Invalid or expired authorization state')
    claim = s.execute(update(BrokerAuthState).where(BrokerAuthState.id == row.id, BrokerAuthState.consumed == False).values(consumed=True))
    if claim.rowcount != 1:
        s.rollback()
        raise HTTPException(400, 'Authorization state already consumed')
    set_context(s, row.user_id)
    account = owned(s, BrokerAccount, row.account_id, row.user_id)
    s.commit()
    try:
        config = integration(s, broker)
        user = s.get(User, row.user_id)
        if not user or not user.active or (not user.verified) or (account.status == 'disconnected'):
            raise ValueError()
        credential = s.scalar(select(BrokerCredential).where(BrokerCredential.account_id == account.id, BrokerCredential.user_id == row.user_id))
        from app.security.encryption import open_credentials
        payload = open_credentials(row.user_id, account.id, credential.ciphertext)
        if not code:
            raise ValueError()
        tokens = AUTH_ADAPTERS[broker](payload['client_id'], payload['client_secret'], config.redirect_uri).exchange(code)
        account = owned(s, BrokerAccount, row.account_id, row.user_id, lock=True)
        if account.status == 'disconnected':
            raise ValueError()
        existing = s.scalar(select(BrokerAccount).where(BrokerAccount.broker == broker, BrokerAccount.account_identifier == tokens.account_identifier))
        if existing and existing.user_id != row.user_id:
            raise ValueError('Broker account is already associated with a different customer')
        if existing and existing.id != account.id:
            account.status = 'superseded'
            s.delete(credential)
            s.flush()
            account = existing
            credential = s.scalar(select(BrokerCredential).where(BrokerCredential.account_id == existing.id, BrokerCredential.user_id == row.user_id))
            if not credential:
                credential = BrokerCredential(user_id=row.user_id, account_id=account.id, key_version=settings.encryption_key_version, ciphertext='')
                s.add(credential)
        account.account_identifier = tokens.account_identifier
        account.status = 'connected'
        credential.expires_at = tokens.expires_at
        credential.key_version = settings.encryption_key_version
        credential.ciphertext = seal_credentials(row.user_id, account.id, dict(access_token=tokens.access_token, refresh_token=tokens.refresh_token))
        from app.portfolio.service import connected
        connected(s,row.user_id,account.id,broker)
        audit(s, row.user_id, 'broker_connected:' + broker)
        s.commit()
    except Exception:
        s.rollback()
        account = owned(s, BrokerAccount, row.account_id, row.user_id, lock=True)
        if account.status != 'disconnected':
            account.status = 'failed'
        audit(s, row.user_id, 'broker_auth_failed:' + broker)
        s.commit()
        return RedirectResponse(settings.frontend_url + '/user/broker-and-exchanges?result=failed', status_code=303)
    return RedirectResponse(settings.frontend_url + '/user/broker-and-exchanges?result=connected', status_code=303)

@router.get('/{broker}/status')
def status(broker: str, u=Depends(auth), s: Session=Depends(db)):
    return [account_public(a) for a in s.scalars(select(BrokerAccount).where(BrokerAccount.user_id == u.id, BrokerAccount.broker == broker))]

@router.post('/{broker}/{account_id}/disconnect')
def disconnect(broker: str, account_id: str, u=Depends(auth), s: Session=Depends(db)):
    account = owned(s, BrokerAccount, account_id, u.id, lock=True)
    if account.broker != broker:
        raise HTTPException(404, 'Record not found')
    account.status = 'disconnected'
    account.live_authorized = False
    account.kill_switch = True
    s.execute(delete(BrokerCredential).where(BrokerCredential.account_id == account.id, BrokerCredential.user_id == u.id))
    s.execute(update(BrokerAuthState).where(BrokerAuthState.account_id == account.id).values(consumed=True))
    audit(s, u.id, 'broker_disconnected:' + broker)
    s.commit()
    return {'message': 'Local broker session disconnected. Provider-side revocation must be confirmed separately.'}

@router.post('/{broker}/{account_id}/emergency-stop')
def account_stop(broker: str, account_id: str, u=Depends(auth), s: Session=Depends(db)):
    a = owned(s, BrokerAccount, account_id, u.id, lock=True)
    if a.broker != broker:
        raise HTTPException(404, 'Record not found')
    a.kill_switch = True
    a.live_authorized = False
    audit(s, u.id, 'broker_emergency_stop')
    s.commit()
    return {'stopped': True, 'liquidated': False}

class AccountInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    account_id:str

@router.post('/{broker}/disconnect')
def disconnect_selected(broker:str,data:AccountInput,u=Depends(auth),s:Session=Depends(db)):
    return disconnect(broker,data.account_id,u,s)

@router.get('/{broker}/config')
def public_configuration(broker:str,u=Depends(auth),s:Session=Depends(db)):
    if broker not in BROKER_IDS:raise HTTPException(404,'Unknown broker')
    config=s.get(BrokerIntegration,broker)
    return {'broker':broker,'mode':config.mode if config else 'DISABLED','auth_available':bool(config and config.auth_verified and broker in AUTH_ADAPTERS and config.mode!='DISABLED'),'redirect_uri':config.redirect_uri if config else None,'live_trading':False}
