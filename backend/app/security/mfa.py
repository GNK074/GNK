import base64, hashlib, hmac, secrets, struct, time
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
import jwt
from app.core.config import SECRET
from app.database.session import db
from app.models.identity import User, LoginSession
from app.security.authentication import auth, limit
from app.security.encryption import encrypt, decrypt
from app.services.accounts import audit
router = APIRouter(prefix='/api/v1/auth/mfa')

class CodeInput(BaseModel):
    code: str = Field(pattern='^\\d{6}$')

def totp(secret, counter):
    key = base64.b32decode(secret + '=' * ((8 - len(secret) % 8) % 8))
    mac = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = mac[-1] & 15
    return f"{(struct.unpack('>I', mac[offset:offset + 4])[0] & 2147483647) % 1000000:06d}"

def verify_totp(user, code):
    code = ''.join(code.split())
    if not user.mfa_secret or len(code) != 6 or not code.isascii() or not code.isdigit():
        raise HTTPException(401, 'Enter the current 6-digit code from your GNK ALGO authenticator account.')
    secret = decrypt(user.mfa_secret)
    counter = int(time.time() // 30)
    matched = [candidate for candidate in (counter, counter - 1, counter + 1)
               if hmac.compare_digest(totp(secret, candidate), code)]
    fresh = [candidate for candidate in matched if candidate > user.mfa_counter]
    if fresh:
        user.mfa_counter = max(fresh)
        return
    if matched:
        raise HTTPException(401, 'This authenticator code has already been used. Wait for a new code and submit it once.')
    raise HTTPException(401, 'Authenticator code is incorrect or expired. Use the GNK ALGO entry and enable automatic date and time on your phone.')


def current_session(request, s):
    claims = jwt.decode(request.cookies.get('access', ''), SECRET, algorithms=['HS256'], audience='gnk-web', issuer='gnk-api')
    return s.get(LoginSession, claims['sid'])

@router.get('/status')
def status(request: Request, u=Depends(auth), s: Session=Depends(db)):
    return {'enabled': u.mfa_enabled, 'csrf_token': current_session(request, s).csrf}

@router.post('/setup')
def setup(request: Request, u=Depends(auth), s: Session=Depends(db)):
    limit(request, 'mfa-setup', u.id)
    user = s.scalar(select(User).where(User.id == u.id).with_for_update().execution_options(populate_existing=True))
    if user.mfa_enabled:
        raise HTTPException(409, 'MFA already enrolled')
    if not user.mfa_secret:
        user.mfa_secret = encrypt(base64.b32encode(secrets.token_bytes(20)).decode().rstrip('='))
    secret = decrypt(user.mfa_secret)
    s.commit()
    return {'secret': secret, 'provisioning_uri': f'otpauth://totp/GNK%20ALGO:{quote(u.email)}?secret={secret}&issuer=GNK%20ALGO'}

@router.post('/confirm')
def confirm(data: CodeInput, request: Request, u=Depends(auth), s: Session=Depends(db)):
    limit(request, 'mfa-confirm', u.id)
    user = s.scalar(select(User).where(User.id == u.id).with_for_update().execution_options(populate_existing=True))
    verify_totp(user, data.code)
    user.mfa_enabled = True
    current = current_session(request, s)
    for session in s.scalars(select(LoginSession).where(LoginSession.user_id == u.id)):
        if session.id != current.id:
            session.revoked = True
    current.mfa_complete = True
    audit(s, u.id, 'mfa_enabled')
    s.commit()
    return {'message': 'MFA enabled'}
