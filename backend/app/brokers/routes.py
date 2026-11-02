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
    result = []
    aliases = {'angel-one': 'angelone', 'icici-direct': 'icici'}
    for b in BROKERS:
        key = aliases.get(b.lower().replace(' ', '-'), b.lower().replace(' ', '-'))
        config = s.get(BrokerIntegration, key)
        ready = bool(key in AUTH_ADAPTERS and config and config.auth_verified and (config.mode != 'DISABLED'))
        result.append({'id': key, 'name': b, 'status': 'authentication_available' if ready else 'pending_verification', 'supported': False, 'auth_available': ready, 'mode': config.mode if config else 'DISABLED'})
    return result

@router.get('/api/v1/broker-connections')
def connections(u=Depends(auth)):
    return []

@router.post('/api/v1/broker-connections/initiate')
@router.post('/api/v1/broker-connections/manual')
def initiate(u=Depends(auth)):
    raise HTTPException(409, 'Broker integration pending official API, access and compliance verification. No credentials accepted.')
