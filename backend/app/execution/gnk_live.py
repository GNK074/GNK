"""Keep real-money requests distinct from the GNK paper ledger."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.compliance.service import require_disclosure
from app.database.session import db
from app.execution.connection import LiveOrderIntent
from app.execution.live_risk import LiveRiskSource, validate_live_order
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


def live_risk_source() -> LiveRiskSource | None:
    # A trusted live account snapshot provider belongs to the separate execution connection.
    return None


@router.post('/orders', status_code=503)
def submit(data: LiveOrderRequest, user=Depends(require_disclosure),
           s: Session = Depends(db), source: LiveRiskSource | None = Depends(live_risk_source)):
    if source is not None:
        validate_live_order(s, user.id, data.intent(), source)
    # Risk approval alone cannot submit an order or write a synthetic fill.
    raise HTTPException(503, BLOCKER)
