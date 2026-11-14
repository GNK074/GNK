from ipaddress import ip_address
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database.session import db



from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.core.config import now, settings
from app.security.authentication import admin, auth, limit
from app.security.mfa import CodeInput, verify_totp
from app.database.tenancy import set_context
from app.models.identity import User
from app.services.accounts import audit
from sqlalchemy import select
from datetime import timedelta
from zoneinfo import ZoneInfo

router = APIRouter(prefix='/api/v1/ip-management')


def public_address(value: str):
    try:
        address = ip_address(value)
    except ValueError:
        return None
    if not address.is_global or address.is_multicast or getattr(address, 'scope_id', None):
        return None
    return address


@router.get('/current')
def current_connection(request: Request, response: Response, user=Depends(auth)):
    response.headers['Cache-Control'] = 'no-store'
    address = public_address(request.client.host) if request.client else None
    return {
        'public_ip': str(address) if address else None,
        'ip_version': address.version if address else None,
        'detected_at': now(),
        'egress_status': 'configured_unverified' if public_address(settings.broker_egress_ip) else 'not_configured',
    }

class RegistrationDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    broker: Literal['dhan', 'fyers', 'upstox']
    source: Literal['manual', 'connection'] = 'manual'
    primary_ip: str | None = Field(default=None, max_length=15)
    secondary_ip: str | None = Field(default=None, max_length=15)
    ownership_confirmed: Literal[True]


def draft_payload(session, user_id):
    row = session.execute(text(
        'SELECT broker, primary_ip, secondary_ip, updated_at, status FROM static_ip_drafts WHERE user_id=:owner'
    ), {'owner': user_id}).mappings().one_or_none()
    return {'draft': dict(row) if row else None}


@router.get('/registrations')
def read_registration(response: Response, user=Depends(auth), session: Session=Depends(db)):
    response.headers['Cache-Control'] = 'no-store'
    return draft_payload(session, user.id)


@router.put('/registrations')
def save_registration(data: RegistrationDraft, request: Request, response: Response, user=Depends(auth), session: Session=Depends(db)):
    response.headers['Cache-Control'] = 'no-store'
    if data.source == 'connection':
        primary = public_address(request.client.host) if request.client else None
        if not primary or primary.version != 4:
            raise HTTPException(422, 'A public IPv4 connection is required. Enter your broker static IPv4 manually.')
    else:
        primary = public_address(data.primary_ip or '')
    secondary = public_address(data.secondary_ip) if data.secondary_ip else None
    if not primary or primary.version != 4 or (data.secondary_ip and (not secondary or secondary.version != 4 or secondary == primary)):
        raise HTTPException(422, 'Enter distinct public IPv4 addresses.')
    lock_owner(session, user.id)
    existing = draft_payload(session, user.id)['draft']
    if existing and existing['status'] != 'DRAFT':
        raise HTTPException(409, 'This draft has already been submitted.')
    session.execute(text("""
        INSERT INTO static_ip_drafts (user_id, broker, primary_ip, secondary_ip, updated_at)
        VALUES (:owner, :broker, :primary, :secondary, :updated)
        ON CONFLICT (user_id) DO UPDATE SET broker=excluded.broker, primary_ip=excluded.primary_ip,
          secondary_ip=excluded.secondary_ip, updated_at=excluded.updated_at
    """), {'owner': user.id, 'broker': data.broker, 'primary': str(primary),
           'secondary': str(secondary) if secondary else None, 'updated': now()})
    result = draft_payload(session, user.id)
    session.commit()
    return result


def lock_owner(session, owner):
    user = session.scalar(select(User).where(User.id == owner).with_for_update().execution_options(populate_existing=True))
    if not user:
        raise HTTPException(404, 'Account not found')
    return user


@router.post('/registrations/submit')
def submit_registration(data: CodeInput, request: Request, user=Depends(auth), session: Session=Depends(db)):
    limit(request, 'static_ip_submission', user.id)
    owner = lock_owner(session, user.id)
    local_day = now().astimezone(ZoneInfo('Asia/Kolkata')).date()
    week = local_day - timedelta(days=local_day.weekday())
    row = session.execute(text(
        'SELECT status, submitted_week FROM static_ip_drafts WHERE user_id=:owner'
    ), {'owner': owner.id}).mappings().one_or_none()
    if not row or row['status'] != 'DRAFT':
        raise HTTPException(409, 'Save an editable draft before submitting.')
    if row['submitted_week'] == week:
        raise HTTPException(409, 'A request was already submitted this calendar week.')
    if not owner.mfa_enabled:
        raise HTTPException(403, 'Enable your authenticator before submitting a request.')
    verify_totp(owner, data.code)
    session.execute(text("""
        UPDATE static_ip_drafts SET status='PENDING_ADMIN', submitted_week=:week, updated_at=:updated
        WHERE user_id=:owner
    """), {'owner': owner.id, 'week': week, 'updated': now()})
    audit(session, owner.id, 'static_ip_submitted')
    session.commit()
    return {'status': 'PENDING_ADMIN'}


@router.get('/review/{owner_id}')
def review_registration(owner_id: str, response: Response, reviewer=Depends(admin), session: Session=Depends(db)):
    response.headers['Cache-Control'] = 'no-store'
    set_context(session, owner_id)
    return draft_payload(session, owner_id)


class ReviewDecision(BaseModel):
    decision: Literal['approve', 'reject']


@router.post('/review/{owner_id}')
def decide_registration(owner_id: str, data: ReviewDecision, reviewer=Depends(admin), session: Session=Depends(db)):
    if reviewer.id == owner_id:
        raise HTTPException(403, 'Another administrator must review your request.')
    lock_owner(session, owner_id)
    set_context(session, owner_id)
    status = 'PENDING_BROKER' if data.decision == 'approve' else 'DRAFT'
    updated = session.execute(text("""
        UPDATE static_ip_drafts SET status=:status, updated_at=:updated
        WHERE user_id=:owner AND status='PENDING_ADMIN'
    """), {'status': status, 'updated': now(), 'owner': owner_id})
    if updated.rowcount != 1:
        raise HTTPException(409, 'No request is awaiting administrator review.')
    audit(session, reviewer.id, 'static_ip_review_' + data.decision + ':' + owner_id)
    audit(session, owner_id, 'static_ip_approved' if data.decision == 'approve' else 'static_ip_rejected')
    session.commit()
    return {'status': status}
