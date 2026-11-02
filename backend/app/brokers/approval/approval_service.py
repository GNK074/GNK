from sqlalchemy import select
from app.core.config import expired
from app.models.trading import ApprovalRequirement, ApprovalEvidence
from .approval_checks import REQUIREMENTS

def missing_requirements(s, broker):
    rows = {r.requirement: r for r in s.scalars(select(ApprovalRequirement).where(ApprovalRequirement.broker == broker))}
    missing = []
    for number in REQUIREMENTS:
        row = rows.get(number)
        evidence = s.scalar(select(ApprovalEvidence).where(ApprovalEvidence.requirement_id == row.id).order_by(ApprovalEvidence.created_at.desc())) if row else None
        if not row or not row.passed or (not evidence) or expired(evidence.expires_at):
            missing.append(number)
    return missing
