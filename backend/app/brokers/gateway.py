from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import expired
from app.models.trading import BrokerAccount, BrokerCredential


def account_public(a):
    return dict(id=a.id, broker=a.broker, account_identifier='***' + a.account_identifier[-4:] if a.account_identifier else None, status=a.status, live_authorized=a.live_authorized, kill_switch=a.kill_switch)


def connections(u, s: Session):
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
