from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import db
from app.security.authentication import auth
from app.execution.routes import risk_for
from app.services.accounts import audit
router = APIRouter()

@router.post('/api/v1/emergency-stop')
def stop(u=Depends(auth), s: Session=Depends(db)):
    risk_for(s, u.id).kill_switch = True
    audit(s, u.id, 'emergency_stop')
    s.commit()
    return {'message': 'Emergency stop active. New paper orders blocked; live execution is unavailable.', 'liquidated': False}
