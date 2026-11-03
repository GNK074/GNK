"""Recovery requires password + saved code + email, or email + reviewed admin approval."""
import secrets
from datetime import timedelta
from typing import Literal
from argon2.exceptions import VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select, update, func
from sqlalchemy.orm import Session
from app.core.config import ORIGIN, digest, expired, now
from app.database.session import db
from app.database.tenancy import set_context
from app.models.identity import User, Token, MfaRecoveryCode, MfaRecoveryRequest
from app.security.authentication import auth, admin, hasher, limit
from app.security.mfa import verify_totp
from app.services import accounts
router = APIRouter(prefix='/api/v1/auth/mfa')
review_router = APIRouter(prefix='/api/v1/admin/mfa-recovery')

class RecoveryInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: EmailStr
    password: str = Field(min_length=1,max_length=128)
    recovery_code: str | None = Field(default=None,max_length=40)

class TokenProof(BaseModel):
    token: str = Field(min_length=20,max_length=100)

class StepUp(BaseModel):
    current_password: str = Field(max_length=128)
    code: str = Field(pattern='^[0-9]{6}$')

class Approval(StepUp):
    identity_verified: Literal[True]

def issue_codes(s, user):
    s.execute(update(MfaRecoveryCode).where(MfaRecoveryCode.user_id==user.id).values(used=True))
    s.execute(update(MfaRecoveryRequest).where(MfaRecoveryRequest.user_id==user.id).values(consumed=True))
    codes=[]
    for _ in range(10):
        raw=secrets.token_hex(10)
        codes.append(raw[:10]+'-'+raw[10:])
        s.add(MfaRecoveryCode(user_id=user.id,code_hash=digest(user.id+':'+raw)))
    return codes

def step_up(s,u,data):
    current=s.scalar(select(User).where(User.id==u.id).with_for_update().execution_options(populate_existing=True))
    if not current or not current.active or not current.verified:
        raise HTTPException(403,'Account unavailable')
    if not current.mfa_enabled:
        raise HTTPException(403,'An enrolled authenticator is required for this action')
    try:
        hasher.verify(current.password,data.current_password)
    except VerificationError:
        raise HTTPException(401,'Current password is incorrect')
    verify_totp(current,data.code)
    return current

@router.get('/recovery/codes/status')
def code_status(u=Depends(auth),s: Session=Depends(db)):
    return {'remaining':s.scalar(select(func.count()).select_from(MfaRecoveryCode).where(MfaRecoveryCode.user_id==u.id,MfaRecoveryCode.used==False))}

@router.post('/recovery/codes')
def regenerate(data: StepUp,request: Request,u=Depends(auth),s: Session=Depends(db)):
    limit(request,'mfa-backup-generate',u.id)
    current=step_up(s,u,data)
    codes=issue_codes(s,current)
    accounts.audit(s,u.id,'mfa_recovery_codes_generated')
    s.commit()
    return {'recovery_codes':codes,'message':'Save these codes privately. They are shown only once; previous codes no longer work.'}

@router.post('/recovery/request',status_code=202)
def request_recovery(data: RecoveryInput,request: Request,s: Session=Depends(db)):
    limit(request,'mfa-recovery',data.email)
    message={'message':'If the details are eligible, a confirmation link has been emailed. Without a saved recovery code, verified administrator review is also required.'}
    user=s.scalar(select(User).where(User.email==str(data.email).lower()).with_for_update())
    try:
        if not user:
            hasher.verify(hasher.hash('dummy-password'),data.password)
            return message
        hasher.verify(user.password,data.password)
    except VerificationError:
        return message
    if not user.active or not user.verified or not user.mfa_enabled:
        return message
    set_context(s,user.id)
    backup=False
    if data.recovery_code:
        normalized=''.join(data.recovery_code.lower().replace('-','').split())
        saved=s.scalar(select(MfaRecoveryCode).where(MfaRecoveryCode.user_id==user.id,MfaRecoveryCode.code_hash==digest(user.id+':'+normalized),MfaRecoveryCode.used==False).with_for_update())
        if not saved:
            return message
        saved.used=True
        backup=True
    s.execute(update(MfaRecoveryRequest).where(MfaRecoveryRequest.user_id==user.id).values(consumed=True))
    raw=secrets.token_urlsafe(32)
    pending=MfaRecoveryRequest(user_id=user.id,email_token_hash=digest(raw),backup_verified=backup,expires=now()+timedelta(minutes=20))
    s.add(pending)
    s.flush()
    accounts.send_email(user.email,'Confirm your GNK ALGO MFA recovery',f'{ORIGIN}/mfa-recovery?token={raw}')
    accounts.audit(s,user.id,'mfa_recovery_requested')
    s.commit()
    return message

def complete(s,user,pending,actor=None):
    user.mfa_secret=None
    user.mfa_enabled=False
    user.mfa_counter=-1
    user.mfa_reenroll_required=True
    pending.approved_by=actor
    s.execute(update(MfaRecoveryRequest).where(MfaRecoveryRequest.user_id==user.id).values(consumed=True))
    s.execute(update(Token).where(Token.user_id==user.id).values(used=True))
    set_context(s,user.id)
    s.execute(update(MfaRecoveryCode).where(MfaRecoveryCode.user_id==user.id).values(used=True))
    accounts.revoke_all(s,user.id)
    accounts.audit(s,user.id,'mfa_recovered_by_admin' if actor else 'mfa_recovered_with_backup')
    if actor:
        accounts.audit(s,actor,'mfa_recovery_approved:'+pending.id)
    accounts.send_email(user.email,'GNK ALGO authenticator recovery completed','Your authenticator was reset after verified recovery. All sessions were signed out. Sign in and enroll a new authenticator before accessing your workspace.')
    s.commit()

@router.post('/recovery/confirm')
def confirm_recovery(data: TokenProof,request: Request,s: Session=Depends(db)):
    limit(request,'mfa-recovery-confirm')
    found=s.scalar(select(MfaRecoveryRequest).where(MfaRecoveryRequest.email_token_hash==digest(data.token)))
    if not found:
        raise HTTPException(400,'Invalid or expired recovery link')
    user=s.scalar(select(User).where(User.id==found.user_id).with_for_update())
    pending=s.scalar(select(MfaRecoveryRequest).where(MfaRecoveryRequest.id==found.id).with_for_update().execution_options(populate_existing=True))
    if pending.consumed or expired(pending.expires) or not user.active or not user.verified:
        raise HTTPException(400,'Invalid or expired recovery link')
    if pending.email_confirmed:
        raise HTTPException(400,'This email confirmation link has already been used')
    pending.email_confirmed=True
    if pending.backup_verified:
        complete(s,user,pending)
        return {'completed':True,'message':'MFA recovery verified. Sign in and set up a new authenticator.'}
    pending.expires=now()+timedelta(hours=24)
    accounts.audit(s,user.id,'mfa_recovery_email_verified')
    s.commit()
    return {'completed':False,'message':'Email confirmed. A super administrator must verify your identity and approve recovery. MFA remains enabled until approval.'}

@review_router.get('/requests')
def pending_requests(u=Depends(admin),s: Session=Depends(db)):
    if u.role!='SUPER_ADMIN':
        raise HTTPException(403,'Super administrator required')
    rows=s.execute(select(MfaRecoveryRequest,User.email).join(User,User.id==MfaRecoveryRequest.user_id).where(MfaRecoveryRequest.consumed==False,MfaRecoveryRequest.email_confirmed==True,MfaRecoveryRequest.expires>now()).order_by(MfaRecoveryRequest.created.desc()).limit(100))
    return [{'id':r.id,'email':email,'created':r.created,'expires':r.expires} for r,email in rows]

@review_router.post('/requests/{record_id}/approve')
def approve(record_id: str,data: Approval,request: Request,u=Depends(admin),s: Session=Depends(db)):
    if u.role!='SUPER_ADMIN':
        raise HTTPException(403,'Super administrator required')
    limit(request,'mfa-recovery-approve',u.id)
    current=step_up(s,u,data)
    if current.role!='SUPER_ADMIN':
        raise HTTPException(403,'Super administrator required')
    found=s.get(MfaRecoveryRequest,record_id)
    if not found or found.user_id==u.id:
        raise HTTPException(403,'This recovery request cannot be approved here')
    target=s.scalar(select(User).where(User.id==found.user_id).with_for_update())
    pending=s.scalar(select(MfaRecoveryRequest).where(MfaRecoveryRequest.id==record_id).with_for_update().execution_options(populate_existing=True))
    if not target.active or not target.verified or target.role=='SUPER_ADMIN' or pending.consumed or not pending.email_confirmed or expired(pending.expires):
        raise HTTPException(409,'Request is not eligible for approval')
    complete(s,target,pending,current.id)
    return {'message':'Recovery approved. The user must sign in and enroll a new authenticator.'}
