from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.session import db
from app.security.authentication import cache
from fastapi import APIRouter
router = APIRouter()

@router.get('/api/v1/health')
def health(s: Session=Depends(db)):
    s.execute(select(1))
    cache.ping()
    return {'status': 'ok', 'live_trading': False}
