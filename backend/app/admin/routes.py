from fastapi import Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.api.health import health
from app.database.session import db
from app.models.identity import Audit, User
from app.schemas.identity import RoleInput, StatusInput
from app.security.authentication import admin
from app.services.accounts import audit, public, revoke_all
from fastapi import APIRouter
router = APIRouter()

@router.get('/api/v1/admin/dashboard')
def stats(u=Depends(admin), s: Session=Depends(db)):
    return {'users': s.scalar(select(func.count(User.id))), 'pending': s.scalar(select(func.count(User.id)).where(User.verified == False)), 'live_trading': False}

@router.get('/api/v1/admin/users')
def users(q: str='', u=Depends(admin), s: Session=Depends(db)):
    return [public(x) for x in s.scalars(select(User).where(User.email.contains(q)).limit(100))]

@router.get('/api/v1/admin/audit-logs')
def logs(u=Depends(admin), s: Session=Depends(db)):
    return [{'event': x.event, 'user_id': x.user_id, 'created': x.created} for x in s.scalars(select(Audit).order_by(Audit.created.desc()).limit(100))]

@router.get('/api/v1/admin/users/{user_id}')
def user_detail(user_id: str, u=Depends(admin), s: Session=Depends(db)):
    target = s.get(User, user_id)
    if not target:
        raise HTTPException(404, 'User not found')
    return public(target)

@router.patch('/api/v1/admin/users/{user_id}/status')
def status_update(user_id: str, data: StatusInput, u=Depends(admin), s: Session=Depends(db)):
    target = s.get(User, user_id)
    if not target:
        raise HTTPException(404, 'User not found')
    if target.role == 'SUPER_ADMIN' or target.id == u.id:
        raise HTTPException(403, 'This account cannot be modified here')
    target.active = data.active
    if not data.active:
        revoke_all(s, target.id)
    audit(s, u.id, 'user_status_changed:' + target.id)
    s.commit()
    return public(target)

@router.patch('/api/v1/admin/users/{user_id}/role')
def role_update(user_id: str, data: RoleInput, u=Depends(admin), s: Session=Depends(db)):
    if u.role != 'SUPER_ADMIN':
        raise HTTPException(403, 'Super administrator required')
    target = s.get(User, user_id)
    if not target:
        raise HTTPException(404, 'User not found')
    if target.role == 'SUPER_ADMIN':
        raise HTTPException(403, 'Cannot alter super administrator')
    target.role = data.role
    revoke_all(s, target.id)
    audit(s, u.id, 'role_changed:' + target.id)
    s.commit()
    return public(target)

@router.get('/api/v1/admin/system-health')
def system_health(u=Depends(admin), s: Session=Depends(db)):
    return health(s)
