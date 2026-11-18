"""Keep real-money requests distinct from the GNK paper ledger."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.compliance.service import require_disclosure
from app.execution.connection import LiveOrderIntent
from app.execution.paper import Price, Quantity
from app.security.authentication import auth

router = APIRouter(prefix='/api/v1/gnk/live', tags=['GNK live trading'])

BLOCKER = 'GNK has no live execution connection configured.'


class LiveOrderRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    client_order_id: str = Field(min_length=8, max_length=80)
    instrument_id: str = Field(min_length=1, max_length=100)
    side: Literal['BUY', 'SELL']
    quantity: Quantity
    limit_price: Price
    confirm_real_money: Literal[True]

    def intent(self):
        return LiveOrderIntent(**self.model_dump(exclude={'confirm_real_money'}))


@router.get('/status')
def status(user=Depends(auth)):
    return {'mode': 'LIVE', 'enabled': False, 'blocker': BLOCKER}


def require_execution_connection(intent: LiveOrderIntent):
    # No real-money execution connection is delivered with GNK core.
    raise HTTPException(503, BLOCKER)


@router.post('/orders', status_code=503)
def submit(data: LiveOrderRequest, user=Depends(require_disclosure)):
    return require_execution_connection(data.intent())
