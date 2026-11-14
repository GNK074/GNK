from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import db
from app.models.identity import Audit
from app.security.authentication import auth

router = APIRouter(prefix='/api/v1/notifications')

MESSAGES = {
    'email_verified': 'Your email address was verified.',
    'password_changed': 'Your account password changed.',
    'password_reset': 'Your account password was reset.',
    'email_changed': 'Your account email address changed.',
    'profile_photo_updated': 'Your profile photo was updated.',
    'session_revoked': 'An account session was revoked.',
    'logout_all': 'Your account was signed out on all devices.',
}


@router.get('')
def inbox(response: Response, user=Depends(auth), session: Session = Depends(db)):
    response.headers['Cache-Control'] = 'no-store'
    events = session.scalars(
        select(Audit).where(Audit.user_id == user.id, Audit.event.in_(MESSAGES))
        .order_by(Audit.created.desc(), Audit.id.desc()).limit(50)
    )
    return {'items': [
        {'id': event.id, 'message': MESSAGES[event.event], 'created': event.created}
        for event in events
    ]}
