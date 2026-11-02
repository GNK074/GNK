import secrets
from datetime import timedelta
from argon2.exceptions import VerificationError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import PROD, digest, expired, now
from app.database.session import db
from app.models.identity import LoginSession, User
from app.schemas.identity import Credentials, EmailInput, PasswordChange, Register, Reset, TokenInput
from app.security.authentication import auth, cookies, hasher, limit
from app.services.accounts import audit, consume, issue, revoke_all
from fastapi import APIRouter
router = APIRouter()

@router.post('/api/v1/auth/register', status_code=202)
def register(data: Register, request: Request, s: Session=Depends(db)):
    limit(request, 'register')
    email = str(data.email).lower()
    if not s.scalar(select(User).where(User.email == email)):
        u = User(email=email, name=data.name.strip(), password=hasher.hash(data.password))
        s.add(u)
        s.flush()
        issue(s, u, 'verify', 60)
        audit(s, u.id, 'registration')
        s.commit()
    return {'message': 'If eligible, a verification email has been sent.'}

@router.post('/api/v1/auth/verify-email')
def verify(data: TokenInput, s: Session=Depends(db)):
    u = consume(s, data.token, 'verify')
    u.verified = True
    audit(s, u.id, 'email_verified')
    s.commit()
    return {'message': 'Email verified. You can sign in.'}

@router.post('/api/v1/auth/login')
def login(data: Credentials, request: Request, response: Response, s: Session=Depends(db)):
    limit(request, 'login')
    u = s.scalar(select(User).where(User.email == str(data.email).lower()))
    try:
        if not u:
            hasher.verify(hasher.hash('dummy-password'), data.password)
            raise ValueError()
        hasher.verify(u.password, data.password)
    except (VerificationError, ValueError):
        audit(s, u.id if u else None, 'login_failed')
        s.commit()
        raise HTTPException(401, 'Invalid credentials')
    if not u.verified or not u.active:
        raise HTTPException(403, 'Verify your email and ensure your account is active')
    raw = secrets.token_urlsafe(48)
    session = LoginSession(user_id=u.id, refresh_hash=digest(raw), csrf=secrets.token_hex(32), expires=now() + timedelta(days=30), agent=request.headers.get('user-agent', '')[:300])
    s.add(session)
    audit(s, u.id, 'login')
    s.commit()
    return cookies(response, u, session, raw)

@router.post('/api/v1/auth/refresh')
def refresh(request: Request, response: Response, s: Session=Depends(db)):
    limit(request, 'refresh')
    session = s.scalar(select(LoginSession).where(LoginSession.refresh_hash == digest(request.cookies.get('refresh', ''))).with_for_update())
    if not session or session.revoked or expired(session.expires):
        raise HTTPException(401, 'Session expired')
    if not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session.csrf):
        raise HTTPException(403, 'Invalid CSRF token')
    u = s.get(User, session.user_id)
    if not u.active or not u.verified:
        raise HTTPException(401, 'Account unavailable')
    raw = secrets.token_urlsafe(48)
    session.refresh_hash = digest(raw)
    session.csrf = secrets.token_hex(32)
    s.commit()
    return cookies(response, u, session, raw)

@router.post('/api/v1/auth/logout-all')
@router.post('/api/v1/auth/logout')
def logout(response: Response, u=Depends(auth), s: Session=Depends(db)):
    revoke_all(s, u.id)
    audit(s, u.id, 'logout_all')
    s.commit()
    for key in ('access', 'refresh'):
        response.delete_cookie(key, path='/api/v1', secure=PROD, httponly=True, samesite='strict')
    return {'message': 'Signed out of all devices'}

@router.post('/api/v1/auth/forgot-password')
@router.post('/api/v1/auth/resend-verification')
def recovery(data: EmailInput, request: Request, s: Session=Depends(db)):
    limit(request, 'recovery')
    u = s.scalar(select(User).where(User.email == str(data.email).lower()))
    kind = 'reset' if request.url.path.endswith('forgot-password') else 'verify'
    if u and u.active and (kind == 'reset' or not u.verified):
        issue(s, u, kind, 20)
        s.commit()
    return {'message': 'If eligible, an email has been sent.'}

@router.post('/api/v1/auth/reset-password')
def reset(data: Reset, s: Session=Depends(db)):
    u = consume(s, data.token, 'reset')
    u.password = hasher.hash(data.password)
    revoke_all(s, u.id)
    audit(s, u.id, 'password_reset')
    s.commit()
    return {'message': 'Password updated. Please sign in.'}

@router.post('/api/v1/auth/change-password')
def change_password(data: PasswordChange, u=Depends(auth), s: Session=Depends(db)):
    current = s.get(User, u.id)
    try:
        hasher.verify(current.password, data.current_password)
    except VerificationError:
        raise HTTPException(400, 'Current password is incorrect')
    current.password = hasher.hash(data.password)
    revoke_all(s, u.id)
    audit(s, u.id, 'password_changed')
    s.commit()
    return {'message': 'Password changed. All sessions revoked. Please sign in again.'}
