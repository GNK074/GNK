from urllib.parse import urlsplit
import jwt
import secrets
from datetime import timedelta
from argon2.exceptions import VerificationError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import PROD, ORIGIN, SECRET, digest, expired, now, settings
from app.database.session import db
from app.models.identity import LoginSession, User, Token, MfaRecoveryRequest
from app.schemas.identity import Credentials, EmailInput, PasswordChange, Register, Reset, TokenInput, EmailChange
from app.security.authentication import auth, cookies, hasher, limit
from app.services.accounts import audit, consume, issue, revoke_all
from fastapi import APIRouter
router = APIRouter()

@router.post('/api/v1/auth/register', status_code=202)
def register(data: Register, request: Request, s: Session=Depends(db)):
    limit(request, 'register', data.email)
    email = str(data.email).lower()
    if not s.scalar(select(User).where(User.email == email)):
        u = User(email=email, name=data.name.strip(), password=hasher.hash(data.password), gender=data.gender, date_of_birth=data.date_of_birth, mobile=data.mobile)
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
    limit(request, 'login', data.email)
    # Lock before password/MFA verification so concurrent requests observe the latest counter.
    u = s.scalar(select(User).where(User.email == str(data.email).lower()).with_for_update())
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
    if u.mfa_enabled:
        from app.security.mfa import verify_totp
        verify_totp(u, data.totp_code or '')
    raw = secrets.token_urlsafe(48)
    session = LoginSession(mfa_complete=(u.mfa_enabled or not settings.enable_mfa) and not u.mfa_reenroll_required, user_id=u.id, refresh_hash=digest(raw), csrf=secrets.token_hex(32), expires=now() + timedelta(days=settings.refresh_token_expire_days), agent=request.headers.get('user-agent', '')[:300])
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
    if not session.mfa_complete:
        raise HTTPException(403, 'Complete MFA enrollment before refreshing')
    if not u.active or not u.verified:
        raise HTTPException(401, 'Account unavailable')
    raw = secrets.token_urlsafe(48)
    session.refresh_hash = digest(raw)
    session.csrf = secrets.token_hex(32)
    s.commit()
    return cookies(response, u, session, raw)

def logout_origin(request):
    origin=request.headers.get('origin')
    permitted=not origin or origin.rstrip('/') in {x.rstrip('/') for x in settings.origins}
    if origin and not permitted:
        # A configured reverse proxy may serve the same app on an additional
        # host (for example www). Accept its own browser origin, never an
        # unrelated origin, while retaining the session-bound CSRF requirement.
        try:
            parsed=urlsplit(origin)
            permitted=(parsed.scheme in (('https',) if PROD else ('http','https'))
                and parsed.netloc.lower()==request.headers.get('host','').lower()
                and not parsed.username and not parsed.password
                and parsed.path in ('','/') and not parsed.query and not parsed.fragment)
        except ValueError:permitted=False
    if request.headers.get('sec-fetch-site')=='cross-site' or not permitted:
        raise HTTPException(403,'Sign out must be requested from the application')


def logout_session(request,s,lock=False):
    """Authenticate session revocation without requiring a fresh access JWT/MFA.

    The refresh cookie identifies only its own session; mutations still require
    that session's CSRF token. No token lifetime is extended or rotated here.
    """
    raw=request.cookies.get('refresh','')
    statement=select(LoginSession).where(LoginSession.refresh_hash==digest(raw)) if raw else None
    if statement is not None:
        session=s.scalar(statement)
    else:session=None
    if session is None:
        # Permit logout when only a still-valid access cookie is available.
        try:
            claims=jwt.decode(request.cookies.get('access',''),SECRET,algorithms=['HS256'],audience='gnk-web',issuer='gnk-api',options={'require':['exp','sub','sid']})
            query=select(LoginSession).where(LoginSession.id==claims['sid'],LoginSession.user_id==claims['sub'])
            statement=query
            session=s.scalar(statement)
        except jwt.InvalidTokenError:session=None
    if not session or session.revoked or expired(session.expires):return None
    if lock:
        # Serialize per user before locking sessions, matching login/recovery's
        # lock order and preventing two logout-all requests from deadlocking.
        user=s.scalar(select(User).where(User.id==session.user_id).with_for_update())
        if not user:return None
        session=s.scalar(statement.with_for_update().execution_options(populate_existing=True))
        if not session or session.revoked or expired(session.expires):return None
    return session if s.get(User,session.user_id) else None


@router.get('/api/v1/auth/session')
def session_status(request:Request,s:Session=Depends(db)):
    # Same-origin bootstrap for an expired access cookie or another tab's CSRF
    # rotation. This grants no workspace access and works during MFA enrollment.
    logout_origin(request)
    session=logout_session(request,s)
    if not session:raise HTTPException(401,'Session expired; sign in again to manage other devices')
    return {'csrf_token':session.csrf}


def clear_auth_cookies(response):
    for key in ('access','refresh'):
        response.delete_cookie(key,path='/api/v1',secure=settings.secure_cookies or PROD,httponly=True,samesite='strict')


@router.post('/api/v1/auth/logout-all')
@router.post('/api/v1/auth/logout')
def logout(request:Request,response:Response,s:Session=Depends(db)):
    logout_origin(request)
    session=logout_session(request,s,lock=True)
    all_devices=request.url.path.endswith('logout-all')
    if not session:
        if all_devices:
            raise HTTPException(401,'Your session has expired. Sign in again to sign out other devices, or choose This device.')
        # Idempotent local cleanup for an already expired/revoked session.
        clear_auth_cookies(response)
        return {'message':'Signed out of this device','all_devices':False}
    if not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),session.csrf):
        raise HTTPException(403,'Invalid CSRF token')
    from app.database.tenancy import set_context
    set_context(s,session.user_id)
    if all_devices:revoke_all(s,session.user_id)
    else:session.revoked=True
    audit(s,session.user_id,'logout_all' if all_devices else 'logout')
    s.commit()
    clear_auth_cookies(response)
    return {'message':'Signed out of all devices' if all_devices else 'Signed out of this device','all_devices':all_devices}

@router.post('/api/v1/auth/forgot-password')
@router.post('/api/v1/auth/resend-verification')
def recovery(data: EmailInput, request: Request, s: Session=Depends(db)):
    limit(request, 'recovery', data.email)
    u = s.scalar(select(User).where(User.email == str(data.email).lower()))
    kind = 'reset' if request.url.path.endswith('forgot-password') else 'verify'
    if u and u.active and (kind == 'reset' or not u.verified):
        issue(s, u, kind, 20)
        s.commit()
    return {'message': 'If eligible, an email has been sent.'}

@router.post('/api/v1/auth/reset-password')
def reset(data: Reset, s: Session=Depends(db)):
    u = consume(s, data.token, 'reset')
    s.execute(update(MfaRecoveryRequest).where(MfaRecoveryRequest.user_id == u.id).values(consumed=True))
    u.password = hasher.hash(data.password)
    s.execute(update(Token).where(Token.user_id == u.id).values(used=True))
    revoke_all(s, u.id)
    audit(s, u.id, 'password_reset')
    s.commit()
    return {'message': 'Password updated. Please sign in.'}

@router.post('/api/v1/auth/change-password')
def change_password(data: PasswordChange, request: Request, response: Response, u=Depends(auth), s: Session=Depends(db)):
    limit(request, 'password-change', u.id)
    current = s.get(User, u.id)
    try:
        hasher.verify(current.password, data.current_password)
    except VerificationError:
        raise HTTPException(400, 'Current password is incorrect')
    s.execute(update(MfaRecoveryRequest).where(MfaRecoveryRequest.user_id == u.id).values(consumed=True))
    current.password = hasher.hash(data.password)
    s.execute(update(Token).where(Token.user_id == u.id).values(used=True))
    for key in ('access', 'refresh'):
        response.delete_cookie(key, path='/api/v1', secure=PROD, httponly=True, samesite='strict')
    revoke_all(s, u.id)
    audit(s, u.id, 'password_changed')
    s.commit()
    return {'message': 'Password changed. All sessions revoked. Please sign in again.'}


@router.post('/api/v1/auth/change-email', status_code=202)
def request_email_change(data: EmailChange, request: Request, u=Depends(auth), s: Session=Depends(db)):
    limit(request, 'email-change', u.id)
    current = s.scalar(select(User).where(User.id == u.id).with_for_update())
    try:
        hasher.verify(current.password, data.current_password)
    except VerificationError:
        raise HTTPException(400, 'Current password is incorrect')
    target = str(data.email).lower()
    if target == current.email:
        raise HTTPException(400, 'Enter a different email address')
    # Do not reveal whether the target address belongs to another account.
    if not s.scalar(select(User.id).where(User.email == target)):
        s.execute(update(Token).where(Token.user_id == u.id, Token.kind == 'change-email').values(used=True))
        raw = secrets.token_urlsafe(32)
        s.add(Token(id=digest(raw), user_id=u.id, kind='change-email', target_email=target, expires=now() + timedelta(minutes=20)))
        from app.services import accounts
        accounts.send_email(target, 'Confirm your GNK ALGO email address', f'{ORIGIN}/confirm-email-change?token={raw}')
        audit(s, u.id, 'email_change_requested')
        s.commit()
    return {'message': 'If eligible, a confirmation link has been sent to the new address. Your current email remains active until confirmed.'}

@router.post('/api/v1/auth/confirm-email-change')
def confirm_email_change(data: TokenInput, request: Request, s: Session=Depends(db)):
    limit(request, 'email-confirm')
    token = s.scalar(select(Token).where(Token.id == digest(data.token)).with_for_update())
    if not token or token.kind != 'change-email' or token.used or expired(token.expires) or not token.target_email:
        raise HTTPException(400, 'Invalid or expired link')
    current = s.scalar(select(User).where(User.id == token.user_id).with_for_update())
    if not current or not current.active:
        raise HTTPException(400, 'Account unavailable')
    try:
        s.execute(update(MfaRecoveryRequest).where(MfaRecoveryRequest.user_id == current.id).values(consumed=True))
        current.email = token.target_email
        current.verified = True
        token.used = True
        s.execute(update(Token).where(Token.user_id == current.id).values(used=True))
        revoke_all(s, current.id)
        audit(s, current.id, 'email_changed')
        s.commit()
    except IntegrityError:
        s.rollback()
        raise HTTPException(400, 'This email change can no longer be completed')
    return {'message': 'Email updated. Sign in with your new address.'}
