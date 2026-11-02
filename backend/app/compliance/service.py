from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import now, settings
from app.database.session import db
from app.security.authentication import auth
from app.api.users import session_id
from app.compliance.models import DisclosureAcknowledgment
from app.compliance.content import document

def period_key():
    return f'{settings.disclosure_max_age_hours}:' + str(int(now().timestamp()) // (settings.disclosure_max_age_hours * 3600))

def receipt(s, uid, sid, doc):
    return s.scalar(select(DisclosureAcknowledgment).where(
        DisclosureAcknowledgment.user_id == uid, DisclosureAcknowledgment.session_id == sid,
        DisclosureAcknowledgment.disclosure_id == doc['id'], DisclosureAcknowledgment.disclosure_version == doc['version'],
        DisclosureAcknowledgment.content_sha256 == doc['content_sha256'], DisclosureAcknowledgment.period_key == period_key()))

def require_disclosure(request: Request, u=Depends(auth), s: Session=Depends(db)):
    if not receipt(s, u.id, session_id(request), document()):
        raise HTTPException(428, {'code': 'DISCLOSURE_REQUIRED', 'message': 'Read and acknowledge the current risk disclosure before placing orders.'})
    return u
