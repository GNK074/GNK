from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import db
from app.models.trading import BrokerIntegration
from app.brokers.registry import AUTH_ADAPTERS
from app.security.authentication import auth
from fastapi import APIRouter
router = APIRouter()
BROKERS = ['Dhan', 'Zerodha', 'Upstox', 'Angel One', 'FYERS', '5paisa', 'ICICI Direct', 'Kotak Neo', 'Alice Blue', 'Shoonya', 'Motilal Oswal', 'Sharekhan']

@router.get('/api/v1/brokers')
def brokers(u=Depends(auth), s: Session=Depends(db)):
    from app.brokers.individual.routes import setup_payload
    result = []
    aliases = {'angel-one': 'angelone', 'icici-direct': 'icici'}
    for b in BROKERS:
        key = aliases.get(b.lower().replace(' ', '-'), b.lower().replace(' ', '-'))
        config = s.get(BrokerIntegration, key)
        ready = bool(key in AUTH_ADAPTERS and config and config.auth_verified and (config.mode != 'DISABLED'))
        setup=setup_payload(s,key)
        result.append({**setup,'id': key, 'name': b, 'status': 'connect_with_your_credentials' if setup['individual_available'] else ('authentication_available' if ready else 'setup_required'), 'supported': False, 'auth_available': ready, 'mode': config.mode if config else ('INDIVIDUAL' if setup['individual_available'] else 'DISABLED')})
    return result

@router.get('/api/v1/broker-connections')
def connections(u=Depends(auth),s:Session=Depends(db)):
    from app.brokers.gateway import connections as current_connections
    return current_connections(u,s)

@router.post('/api/v1/broker-connections/initiate')
@router.post('/api/v1/broker-connections/manual')
def initiate(u=Depends(auth)):
    raise HTTPException(409, 'Broker integration pending official API, access and compliance verification. No credentials accepted.')
