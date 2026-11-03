from .jobs import enqueue
from app.market_data.config import market_settings as cfg
from fastapi import HTTPException

def enqueue_instruments(s,user_id=None):
    if not cfg.upstox_instrument_sync_enabled:raise HTTPException(409,'Instrument sync is disabled')
    return enqueue(s,'INSTRUMENTS',{},user_id)
