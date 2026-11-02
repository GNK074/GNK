import secrets
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import ORIGIN, digest, expired, now
from app.models.identity import Audit, LoginSession, Token, User
from app.notifications.email import send_email

def audit(s, user_id, event):
    s.add(Audit(user_id=user_id, event=event))

def issue(s, user, kind, minutes):
    raw = secrets.token_urlsafe(32)
    s.add(Token(id=digest(raw), user_id=user.id, kind=kind, expires=now() + timedelta(minutes=minutes)))
    s.flush()
    send_email(user.email, 'Verify your email' if kind == 'verify' else 'Reset your password', f'{ORIGIN}/{kind}?token={raw}')

def consume(s, raw, kind):
    token = s.scalar(select(Token).where(Token.id == digest(raw)).with_for_update())
    if not token or token.kind != kind or token.used or expired(token.expires):
        raise HTTPException(400, 'Invalid or expired token')
    token.used = True
    return s.get(User, token.user_id)

def revoke_all(s, uid):
    for item in s.scalars(select(LoginSession).where(LoginSession.user_id == uid)):
        item.revoked = True

def public(u):
    return dict(id=u.id, name=u.name, email=u.email, verified=u.verified, active=u.active, role=u.role, theme=u.theme, avatar_url=f'/api/v1/users/me/avatar?v={u.avatar_version}' if u.avatar_version > 0 else None)
