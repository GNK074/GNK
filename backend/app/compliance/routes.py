from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database.session import db
from app.security.authentication import auth
from app.api.users import session_id
from app.models.identity import LoginSession
from app.services.accounts import audit
from app.compliance.content import document
from app.compliance.models import DisclosureAcknowledgment
from app.compliance.service import receipt, period_key
router = APIRouter(prefix='/api/v1/compliance/disclosure')

class Acknowledge(BaseModel):
    model_config = ConfigDict(extra='forbid')
    disclosure_id: str = Field(max_length=60)
    disclosure_version: str = Field(max_length=100)
    content_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    acknowledged: Literal[True]

@router.get('')
def disclosure(u=Depends(auth)):
    return document()

@router.get('/status')
def status(request: Request, u=Depends(auth), s: Session=Depends(db)):
    doc = document()
    item = receipt(s, u.id, session_id(request), doc)
    return {'required': item is None, 'disclosure_id': doc['id'], 'disclosure_version': doc['version'], 'frequency': doc['frequency'], 'acknowledged_at': item.acknowledged_at if item else None}

@router.post('/acknowledge')
def acknowledge(data: Acknowledge, request: Request, u=Depends(auth), s: Session=Depends(db)):
    doc = document()
    if (data.disclosure_id, data.disclosure_version, data.content_sha256) != (doc['id'], doc['version'], doc['content_sha256']):
        raise HTTPException(409, 'Disclosure changed. Reload and read the current version.')
    sid = session_id(request)
    # Serialize double clicks/retries on this login; the unique constraint is a second guard.
    s.scalar(select(LoginSession).where(LoginSession.id == sid, LoginSession.user_id == u.id).with_for_update())
    item = receipt(s, u.id, sid, doc)
    if not item:
        item = DisclosureAcknowledgment(user_id=u.id, session_id=sid, disclosure_id=doc['id'], disclosure_version=doc['version'], content_sha256=doc['content_sha256'], period_key=period_key())
        s.add(item)
        audit(s, u.id, 'risk_disclosure_acknowledged')
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            item = receipt(s, u.id, sid, doc)
            if not item:
                raise
    return {'required': False, 'disclosure_version': doc['version'], 'acknowledged_at': item.acknowledged_at}
