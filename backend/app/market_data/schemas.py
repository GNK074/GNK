from datetime import date,datetime
from zoneinfo import ZoneInfo
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
Mode=Literal['ltpc','full','option_greeks']
INTERVALS={'1m':('minutes',1),'2m':('minutes',2),'3m':('minutes',3),'5m':('minutes',5),'10m':('minutes',10),'15m':('minutes',15),'30m':('minutes',30),'1h':('hours',1),'2h':('hours',2),'4h':('hours',4),'1d':('days',1),'1w':('weeks',1),'1M':('months',1)}

class SubscribeInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    instrument_keys: list[str]=Field(min_length=1,max_length=100)
    mode: Mode='ltpc'

class HistoryInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    instrument_id: str=Field(min_length=1,max_length=36)
    interval: str='1m'
    from_date: date
    to_date: date
    @model_validator(mode='after')
    def valid_dates(self):
        if self.interval not in INTERVALS or self.from_date>self.to_date or self.to_date>datetime.now(ZoneInfo('Asia/Kolkata')).date():
            raise ValueError('Invalid interval or date range')
        minimum=date(2022,1,1) if INTERVALS[self.interval][0] in ('minutes','hours') else date(2000,1,1)
        if self.from_date<minimum or (self.to_date-self.from_date).days>3660:
            raise ValueError('Date range exceeds supported historical availability')
        return self

class EntitlementInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled: bool
    segments: list[str]=Field(min_length=1,max_length=6)
    modes: list[Mode]=Field(min_length=1,max_length=3)
    max_instruments: int=Field(default=50,ge=1,le=500)
    expires_at: datetime|None=None
