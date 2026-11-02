from fastapi import Depends
from sqlalchemy.orm import Session
from app.database.session import db
from app.security.authentication import auth
from app.services.accounts import audit
from fastapi import APIRouter
router = APIRouter()

@router.post('/api/v1/emergency-stop')
def stop(u=Depends(auth), s: Session=Depends(db)):
    audit(s, u.id, 'emergency_stop')
    s.commit()
    return {'message': 'Emergency stop recorded. Live trading is disabled.'}
