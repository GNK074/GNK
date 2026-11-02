from fastapi import Depends, HTTPException
from app.security.authentication import auth
from fastapi import APIRouter
router = APIRouter()
BROKERS = ['Dhan', 'Zerodha', 'Upstox', 'Angel One', 'FYERS', '5paisa', 'ICICI Direct', 'Kotak Neo', 'Alice Blue', 'Shoonya', 'Motilal Oswal', 'Sharekhan']

@router.get('/api/v1/brokers')
def brokers(u=Depends(auth)):
    return [{'id': b.lower().replace(' ', '-'), 'name': b, 'status': 'pending_verification', 'supported': False} for b in BROKERS]

@router.get('/api/v1/broker-connections')
def connections(u=Depends(auth)):
    return []

@router.post('/api/v1/broker-connections/initiate')
@router.post('/api/v1/broker-connections/manual')
def initiate(u=Depends(auth)):
    raise HTTPException(409, 'Broker integration pending official API, access and compliance verification. No credentials accepted.')
