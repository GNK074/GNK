from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class StrategyInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=2, max_length=100)

class RiskInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    max_quantity: int = Field(default=100, ge=1, le=100000)
    max_order_value: Decimal = Field(default=100000, gt=0, le=10000000, max_digits=20, decimal_places=4)
    max_daily_orders: int = Field(default=50, ge=1, le=10000)
    max_daily_loss: Decimal = Field(default=5000, gt=0, max_digits=20, decimal_places=4)
    max_positions: int = Field(default=3, ge=1, le=1000)

class PaperOrderInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    strategy_id: str
    symbol: str = Field(pattern='^[A-Z0-9_.-]{1,40}$')
    side: Literal['BUY', 'SELL']
    quantity: int = Field(ge=1, le=100000)
    price: Decimal = Field(gt=0, le=10000000, max_digits=20, decimal_places=4)
    idempotency_key: str = Field(min_length=8, max_length=80)

class SwitchInput(BaseModel):
    enabled: bool

class LiveOrderInput(PaperOrderInput):
    broker_account_id: str
    instrument_id: str | None = None
    confirm_real_money: bool = False
