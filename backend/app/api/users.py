import jwt
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import SECRET
from app.database.session import db
from app.models.identity import Audit, LoginSession, User
from app.schemas.identity import Profile
from app.security.authentication import auth
from app.services.accounts import audit, public
from fastapi import APIRouter
router = APIRouter()

@router.get('/api/v1/users/me')
def me(request: Request, u=Depends(auth), s: Session=Depends(db)):
    claims = jwt.decode(request.cookies['access'], SECRET, algorithms=['HS256'], audience='gnk-web', issuer='gnk-api')
    return {'user': public(u), 'csrf_token': s.get(LoginSession, claims['sid']).csrf}

@router.put('/api/v1/users/me')
def profile(data: Profile, u=Depends(auth), s: Session=Depends(db)):
    s.get(User, u.id).name = data.name.strip()
    audit(s, u.id, 'profile_updated')
    s.commit()
    return {'message': 'Profile saved'}

@router.get('/api/v1/users/me/sessions')
def sessions(u=Depends(auth), s: Session=Depends(db)):
    return [{'id': x.id, 'agent': x.agent, 'created': x.created, 'revoked': x.revoked} for x in s.scalars(select(LoginSession).where(LoginSession.user_id == u.id))]

@router.get('/api/v1/users/me/login-history')
def history(u=Depends(auth), s: Session=Depends(db)):
    return [{'event': x.event, 'created': x.created} for x in s.scalars(select(Audit).where(Audit.user_id == u.id).order_by(Audit.created.desc()).limit(100))]
