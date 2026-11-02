import io
import warnings
import jwt
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.core.config import SECRET, expired
from app.database.session import db
from app.models.identity import Audit, LoginSession, User
from app.schemas.identity import Profile, Preferences
from app.security.authentication import auth, limit
from app.services.accounts import audit, public
router = APIRouter()
MAX_PHOTO_BYTES = 2 * 1024 * 1024

def own_profile(u):
    return {**public(u), 'gender': u.gender, 'date_of_birth': u.date_of_birth,
            'mobile': u.mobile, 'created': u.created, 'mfa_enabled': u.mfa_enabled}

def session_id(request):
    return jwt.decode(request.cookies['access'], SECRET, algorithms=['HS256'], audience='gnk-web', issuer='gnk-api')['sid']

@router.get('/api/v1/users/me')
def me(request: Request, u=Depends(auth), s: Session=Depends(db)):
    return {'user': own_profile(u), 'csrf_token': s.get(LoginSession, session_id(request)).csrf}

@router.put('/api/v1/users/me')
def profile(data: Profile, u=Depends(auth), s: Session=Depends(db)):
    current = s.get(User, u.id)
    if len(data.name.strip()) < 2:
        raise HTTPException(422, 'Full name must contain at least two characters')
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(current, key, value.strip() if key == 'name' else value)
    audit(s, u.id, 'profile_updated')
    s.commit()
    return {'message': 'Profile saved', 'user': own_profile(current)}

@router.put('/api/v1/users/me/preferences')
def preferences(data: Preferences, u=Depends(auth), s: Session=Depends(db)):
    current = s.get(User, u.id)
    current.theme = data.theme
    s.commit()
    return {'message': 'Appearance saved', 'user': own_profile(current)}

def normalize_photo(raw):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as photo:
                if photo.format not in ('JPEG', 'PNG', 'WEBP') or photo.width * photo.height > 16_000_000:
                    raise ValueError()
                photo.load()
                photo = ImageOps.fit(ImageOps.exif_transpose(photo).convert('RGB'), (512, 512))
                output = io.BytesIO()
                photo.save(output, format='PNG')
                return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, 'Use a valid JPEG, PNG or WebP image up to 16 megapixels')

@router.put('/api/v1/users/me/avatar')
async def upload_avatar(request: Request, u=Depends(auth), s: Session=Depends(db)):
    limit(request, 'avatar', u.id)
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_PHOTO_BYTES:
            raise HTTPException(413, 'Profile photo must be 2 MB or smaller')
    current = s.get(User, u.id)
    current.avatar_data = await run_in_threadpool(normalize_photo, bytes(raw))
    current.avatar_version = abs(current.avatar_version) + 1
    audit(s, u.id, 'profile_photo_updated')
    s.commit()
    return {'message': 'Profile photo updated', 'user': own_profile(current)}

@router.get('/api/v1/users/me/avatar')
def avatar(u=Depends(auth)):
    if not u.avatar_data:
        raise HTTPException(404, 'No profile photo')
    return Response(u.avatar_data, media_type='image/png', headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

@router.delete('/api/v1/users/me/avatar')
def reset_avatar(u=Depends(auth), s: Session=Depends(db)):
    current = s.get(User, u.id)
    current.avatar_data = None
    current.avatar_version = -abs(current.avatar_version) - 1
    audit(s, u.id, 'profile_photo_reset')
    s.commit()
    return {'message': 'Profile photo reset', 'user': own_profile(current)}

@router.get('/api/v1/users/me/sessions')
def sessions(request: Request, u=Depends(auth), s: Session=Depends(db)):
    sid = session_id(request)
    return [{'id': x.id, 'agent': x.agent, 'created': x.created, 'expires': x.expires,
             'revoked': x.revoked, 'current': x.id == sid, 'expired': expired(x.expires)}
            for x in s.scalars(select(LoginSession).where(LoginSession.user_id == u.id).order_by(LoginSession.created.desc()).limit(100))]

@router.delete('/api/v1/users/me/sessions/{sid}')
def revoke_session(sid: str, u=Depends(auth), s: Session=Depends(db)):
    item = s.scalar(select(LoginSession).where(LoginSession.id == sid, LoginSession.user_id == u.id))
    if not item:
        raise HTTPException(404, 'Session not found')
    item.revoked = True
    audit(s, u.id, 'session_revoked')
    s.commit()
    return {'message': 'Session signed out'}

@router.get('/api/v1/users/me/login-history')
def history(u=Depends(auth), s: Session=Depends(db)):
    return [{'event': x.event, 'created': x.created} for x in s.scalars(select(Audit).where(Audit.user_id == u.id).order_by(Audit.created.desc()).limit(100))]
