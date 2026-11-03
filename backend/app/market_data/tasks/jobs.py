"""Durable jobs executed by the single leased market-data worker."""
import hashlib,json
from sqlalchemy import select,update
from fastapi import HTTPException
from app.core.config import now
from app.market_data.models import MarketSyncJob
from app.market_data.subscription_manager import provider_status

def enqueue(s,kind,parameters,user_id=None):
    provider_status(s)
    from app.market_data.models import MarketProviderStatus
    s.scalar(select(MarketProviderStatus).where(MarketProviderStatus.provider=='upstox').with_for_update())
    key=hashlib.sha256((kind+json.dumps(parameters,sort_keys=True)).encode()).hexdigest()
    found=s.scalar(select(MarketSyncJob).where(MarketSyncJob.dedup_key==key,MarketSyncJob.state.in_(['QUEUED','RUNNING'])))
    if found:return found
    count=len(list(s.scalars(select(MarketSyncJob.id).where(MarketSyncJob.requested_by==user_id,MarketSyncJob.state.in_(['QUEUED','RUNNING'])))))
    if count>=3:raise HTTPException(429,'Wait for pending synchronization jobs to finish')
    job=MarketSyncJob(kind=kind,parameters=parameters,dedup_key=key,requested_by=user_id)
    s.add(job);s.flush();return job
