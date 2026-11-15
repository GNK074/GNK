from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.session import db
from app.models.trading import BrokerAccount, BrokerIntegration
from app.brokers.registry import AUTH_ADAPTERS, BROKER_ALIASES, BROKER_NAMES
from app.security.authentication import auth
from fastapi import APIRouter
router = APIRouter()

def broker_summary(s: Session, key: str) -> dict:
    from app.brokers.individual.routes import setup_payload

    config = s.get(BrokerIntegration, key)
    oauth_available = bool(
        key in AUTH_ADAPTERS and config and config.auth_verified and config.mode != 'DISABLED'
    )
    setup = setup_payload(s, key)
    individual_available = setup['individual_available']
    status = 'setup_required'
    if individual_available:
        status = 'connect_with_your_credentials'
    elif oauth_available:
        status = 'authentication_available'
    return {
        **setup,
        'id': key,
        'name': BROKER_NAMES[key],
        'status': status,
        'supported': False,
        'auth_available': oauth_available,
        'mode': config.mode if config else ('INDIVIDUAL' if individual_available else 'DISABLED'),
    }


@router.get('/api/v1/brokers')
def brokers(u=Depends(auth), s: Session=Depends(db)):
    return [broker_summary(s, key) for key in BROKER_NAMES]


def broker_detail(s: Session, broker: str) -> dict:
    key = BROKER_ALIASES.get(broker, broker)
    if key not in BROKER_NAMES:
        raise HTTPException(404, 'Unknown broker')
    return broker_summary(s, key)


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
