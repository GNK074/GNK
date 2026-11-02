from fastapi import Depends
from app.security.authentication import auth
from fastapi import APIRouter
router = APIRouter()

@router.get('/api/v1/dashboard')
def dashboard(u=Depends(auth)):
    return {'mode': 'disconnected', 'live_trading': False, 'connections': 0, 'portfolio': None, 'strategies': [], 'market_data': None}
