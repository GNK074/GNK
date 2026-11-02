import os
import secrets
from datetime import timedelta
import jwt
import redis
from argon2 import PasswordHasher
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.core.config import PROD, SECRET, expired, now
from app.database.session import db
from app.models.identity import LoginSession, User
from app.services.accounts import public
cache = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379/0'))
hasher = PasswordHasher()

def limit(request, action):
    key = f'rate:{action}:{request.client.host}'
    try:
        count = cache.incr(key)
        if count == 1:
            cache.expire(key, 900)
        if count > 20:
            raise HTTPException(429, 'Too many requests. Try again later.')
    except redis.RedisError:
        raise HTTPException(503, 'Authentication rate limiter unavailable')

def auth(request: Request, s: Session=Depends(db)):
    try:
        claims = jwt.decode(request.cookies.get('access', ''), SECRET, algorithms=['HS256'], audience='gnk-web', issuer='gnk-api')
        session = s.get(LoginSession, claims['sid'])
        user = s.get(User, claims['sub'])
        if not session or session.user_id != user.id or session.revoked or expired(session.expires) or (not user.active) or (not user.verified):
            raise ValueError()
    except Exception:
        raise HTTPException(401, 'Please sign in')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and (not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session.csrf)):
        raise HTTPException(403, 'Invalid CSRF token')
    return user

def admin(u=Depends(auth)):
    if u.role not in ('ADMIN', 'SUPER_ADMIN'):
        raise HTTPException(403, 'Administrator access required')
    return u

def cookies(response, user, session, raw):
    token = jwt.encode(dict(sub=user.id, sid=session.id, iss='gnk-api', aud='gnk-web', exp=now() + timedelta(minutes=15)), SECRET, algorithm='HS256')
    for key, value, age in [('access', token, 900), ('refresh', raw, 2592000)]:
        response.set_cookie(key, value, httponly=True, secure=PROD, samesite='strict', max_age=age, path='/api/v1')
    return {'user': public(user), 'csrf_token': session.csrf}
