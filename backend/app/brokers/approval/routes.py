from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import now, expired, UTC
from app.database.session import db
from app.security.authentication import admin
from app.models.trading import ApprovalRequest, ApprovalRequirement, ApprovalEvidence, ApprovalHistory, ProductionStatus
from .approval_checks import REQUIREMENTS
from .approval_service import missing_requirements
from .approval_schemas import EvidenceInput
router = APIRouter(prefix='/api/v1/admin/brokers')
BROKER_IDS = {'dhan', 'zerodha', 'upstox', 'angelone', 'fyers', '5paisa', 'icici'}

def check(broker, u):
    if u.role != 'SUPER_ADMIN':
        raise HTTPException(403, 'Super administrator required')
    if broker not in BROKER_IDS:
        raise HTTPException(404, 'Unknown broker')

def history(s, broker, u, event):
    s.add(ApprovalHistory(broker=broker, actor=u.id, event=event))

@router.post('/{broker}/approval')
def create(broker: str, u=Depends(admin), s: Session=Depends(db)):
    check(broker, u)
    if s.get(ApprovalRequest, broker):
        raise HTTPException(409, 'Approval request already exists')
    s.add(ApprovalRequest(broker=broker, requested_by=u.id))
    s.flush()
    for number in REQUIREMENTS:
        s.add(ApprovalRequirement(broker=broker, requirement=number))
    history(s, broker, u, 'approval_requested')
    s.commit()
    return {'broker': broker, 'requirements': 18}

@router.get('/{broker}/approval')
@router.get('/{broker}/requirements')
def requirements(broker: str, u=Depends(admin), s: Session=Depends(db)):
    check(broker, u)
    missing = missing_requirements(s, broker)
    return {'broker': broker, 'missing': missing, 'requirements': [{'id': n, 'name': label, 'passed': n not in missing} for n, label in REQUIREMENTS.items()]}

@router.post('/{broker}/requirements/{number}/verify')
def verify_requirement(broker: str, number: int, data: EvidenceInput, u=Depends(admin), s: Session=Depends(db)):
    check(broker, u)
    parent = s.scalar(select(ApprovalRequest).where(ApprovalRequest.broker == broker).with_for_update())
    if not parent or number not in REQUIREMENTS:
        raise HTTPException(404, 'Requirement not found')
    if data.expires_at.tzinfo is None or expired(data.expires_at):
        raise HTTPException(422, 'Evidence requires a future timezone-aware expiry')
    if data.expires_at > now() + timedelta(days=90):
        raise HTTPException(422, 'Evidence expires within 90 days')
    row = s.scalar(select(ApprovalRequirement).where(ApprovalRequirement.broker == broker, ApprovalRequirement.requirement == number))
    row.passed = True
    s.add(ApprovalEvidence(requirement_id=row.id, reference=data.reference, sha256=data.sha256, expires_at=data.expires_at, verified_by=u.id))
    status = s.get(ProductionStatus, broker)
    if status:
        status.approved = False
    history(s, broker, u, f'requirement_verified:{number}')
    s.commit()
    return {'verified': number, 'production_approved': False}

@router.get('/{broker}/production-status')
def production_status(broker: str, u=Depends(admin), s: Session=Depends(db)):
    check(broker, u)
    from app.execution import live_service as live
    status=s.get(ProductionStatus,broker)
    return {'broker':broker,'approved':bool(broker in ('upstox','dhan') and status and status.approved and not missing_requirements(s,broker)), 'missing':missing_requirements(s,broker),'runtime_blocker':None if broker in ('upstox','dhan') else 'Execution adapter not implemented for this broker','server_enabled':live.enabled(broker) if broker=='dhan' else live.enabled(),'reconciliation_healthy':live.worker_ready()}

@router.post('/{broker}/production-approval')
def production_approval(broker: str, u=Depends(admin), s: Session=Depends(db)):
    check(broker, u)
    parent = s.scalar(select(ApprovalRequest).where(ApprovalRequest.broker == broker).with_for_update())
    missing = missing_requirements(s, broker)
    status=s.get(ProductionStatus,broker)
    if not status:
        status=ProductionStatus(broker=broker);s.add(status)
    from app.execution import live_service as live
    from app.core.config import settings
    if not parent or missing or broker not in ('upstox','dhan') or not (live.enabled(broker) if broker=='dhan' else live.enabled()) or not live.worker_ready():
        status.approved=False;status.approved_by=None;status.updated_at=now()
        history(s,broker,u,'production_approval_blocked');s.commit()
        raise HTTPException(409,{'missing_requirements':missing,'runtime_blocker':'Implemented broker adapter, explicit server activation, reconciliation worker and all current evidence are required'})
    status.approved=True;status.approved_by=u.id;status.updated_at=now()
    history(s,broker,u,'production_approved:'+(settings.dhan_execution_reference if broker=='dhan' else settings.live_execution_reference));s.commit()
    return {'broker':broker,'approved':True,'scope':'NSE EQ intraday LIMIT DAY; no short selling'}
