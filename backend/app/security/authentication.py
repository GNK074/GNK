import os
import secrets
from datetime import timedelta
import jwt
import redis
from argon2 import PasswordHasher
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.core.config import PROD, SECRET, expired, now, settings, read_secret, digest
from app.database.session import db
from app.models.identity import LoginSession, User
from app.services.accounts import public
redis_password = read_secret(settings.redis_password_file) if settings.redis_password_file else settings.redis_password.get_secret_value()
cache = redis.Redis.from_url(settings.redis_url.get_secret_value(), password=redis_password or None, max_connections=settings.redis_max_connections, socket_timeout=5, socket_connect_timeout=5)
hasher = PasswordHasher()

def limit(request, action, subject=''):
    buckets = [(f'rate:source:{action}:{request.client.host}', 600)]
    if subject:
        buckets.append((f'rate:subject:{action}:{digest(str(subject).strip().lower())}', 20))
    try:
        for key, maximum in buckets:
            count = cache.eval("local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]); end; return n", 1, key, 900)
            if count > maximum:
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
    if not session.mfa_complete and (not request.url.path.startswith('/api/v1/auth/mfa/')):
        raise HTTPException(403, 'MFA enrollment required')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and (not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session.csrf)):
        raise HTTPException(403, 'Invalid CSRF token')
    from app.database.tenancy import set_context
    set_context(s, user.id)
    return user

def admin(u=Depends(auth)):
    if u.role not in ('ADMIN', 'SUPER_ADMIN'):
        raise HTTPException(403, 'Administrator access required')
    return u

def cookies(response, user, session, raw):
    token = jwt.encode(dict(sub=user.id, sid=session.id, iss='gnk-api', aud='gnk-web', exp=now() + timedelta(minutes=settings.access_token_expire_minutes)), SECRET, algorithm='HS256')
    for key, value, age in [('access', token, settings.access_token_expire_minutes * 60), ('refresh', raw, settings.refresh_token_expire_days * 86400)]:
        response.set_cookie(key, value, httponly=True, secure=settings.secure_cookies or PROD, samesite='strict', max_age=age, path='/api/v1')
    return {'user': public(user), 'csrf_token': session.csrf, 'mfa_required': not session.mfa_complete}
