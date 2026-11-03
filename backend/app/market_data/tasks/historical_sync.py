from .jobs import enqueue
from app.market_data.config import market_settings as cfg
from fastapi import HTTPException

def enqueue_history(s,data,user_id=None,intraday=False):
    if not cfg.upstox_historical_sync_enabled:raise HTTPException(409,'Historical synchronization is disabled')
    return enqueue(s,'INTRADAY' if intraday else 'HISTORY',data,user_id)
