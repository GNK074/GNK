# Internal read-only portfolio bridge.
import hashlib
import hmac
import json
import os
import re
import time

import redis
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database.session import db
from app.database.tenancy import set_context
from app.models.identity import User
from app.security.authentication import cache
from .routes import output, router
from .service import summary

UUID = re.compile(r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}')
HEX = re.compile(r'[0-9a-fA-F]{64}')


@router.get('/bridge/summary')
def bridge_summary(request: Request, s: Session = Depends(db)):
    secret = os.getenv('GNK_PORTFOLIO_SECRET', '')
    if not HEX.fullmatch(secret):
        raise HTTPException(503, 'Portfolio bridge unavailable')
    account = request.headers.get('X-GNK-Account', '')
    issued = request.headers.get('X-GNK-Issued', '')
    nonce = request.headers.get('X-GNK-Nonce', '')
    signature = request.headers.get('X-GNK-Signature', '')
    if not (UUID.fullmatch(account) and UUID.fullmatch(nonce) and re.fullmatch(r'[0-9]{10}', issued) and HEX.fullmatch(signature)):
        raise HTTPException(401, 'Invalid portfolio authorization')
    payload = '\n'.join(('portfolio-summary-v1', account, issued, nonce))
    expected = hmac.new(bytes.fromhex(secret), payload.encode(), hashlib.sha256).hexdigest()
    if abs(time.time() - int(issued)) > 30 or not hmac.compare_digest(expected, signature):
        raise HTTPException(401, 'Invalid portfolio authorization')
    try:
        accepted = cache.set(f'gnk:portfolio:nonce:{nonce}', '1', nx=True, ex=65)
    except redis.RedisError:
        raise HTTPException(503, 'Portfolio bridge unavailable') from None
    if not accepted:
        raise HTTPException(401, 'Invalid portfolio authorization')
    try:
        owner = json.loads((os.getenv('GNK_PORTFOLIO_ACCOUNT_LINKS') or '{}')).get(account)
    except (ValueError, AttributeError):
        raise HTTPException(503, 'Portfolio bridge unavailable') from None
    if not isinstance(owner, str) or not owner:
        raise HTTPException(404, 'Trading account not linked')
    set_context(s, owner)
    user = s.get(User, owner)
    if not user or not user.active or not user.verified:
        raise HTTPException(404, 'Trading account not linked')
    response = output(summary(s, owner))
    response.headers['Cache-Control'] = 'no-store'
    return response
