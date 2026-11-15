from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.session import db
from app.models.trading import BrokerAccount, BrokerIntegration
from app.brokers.registry import AUTH_ADAPTERS, BROKER_NAMES
from app.security.authentication import auth
from fastapi import APIRouter
router = APIRouter()

@router.get('/api/v1/brokers')
def brokers(u=Depends(auth), s: Session=Depends(db)):
    from app.brokers.individual.routes import setup_payload
    result = []
    for key, name in BROKER_NAMES.items():
        config = s.get(BrokerIntegration, key)
        ready = bool(key in AUTH_ADAPTERS and config and config.auth_verified and (config.mode != 'DISABLED'))
        setup=setup_payload(s,key)
        result.append({**setup,'id': key, 'name': name, 'status': 'connect_with_your_credentials' if setup['individual_available'] else ('authentication_available' if ready else 'setup_required'), 'supported': False, 'auth_available': ready, 'mode': config.mode if config else ('INDIVIDUAL' if setup['individual_available'] else 'DISABLED')})
    return result

@router.get('/api/v1/broker-connections')
def connections(u=Depends(auth),s:Session=Depends(db)):
    records = s.execute(
        select(BrokerAccount.id, BrokerAccount.broker)
        .where(BrokerAccount.user_id == u.id, BrokerAccount.status != 'superseded')
        .order_by(BrokerAccount.created_at, BrokerAccount.id)
    )
    return [{'id': account_id, 'broker': broker} for account_id, broker in records]

@router.post('/api/v1/broker-connections/initiate')
@router.post('/api/v1/broker-connections/manual')
def initiate(u=Depends(auth)):
    raise HTTPException(409, 'Broker integration pending official API, access and compliance verification. No credentials accepted.')
