from typing import Literal
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class MarketSettings(BaseSettings):
    model_config=SettingsConfigDict(extra='ignore',hide_input_in_errors=True)
    upstox_enabled: bool=False
    upstox_api_base_url: Literal['https://api.upstox.com']='https://api.upstox.com'
    upstox_analytics_token: SecretStr=SecretStr('')
    upstox_analytics_token_file: str=''
    upstox_client_id: str=''
    upstox_client_secret: SecretStr=SecretStr('')
    upstox_redirect_uri: str=''
    upstox_market_data_mode: Literal['ltpc','full','option_greeks']='ltpc'
    upstox_websocket_enabled: bool=False
    upstox_instrument_sync_enabled: bool=True
    upstox_historical_sync_enabled: bool=False
    marketdata_distribution_approved: bool=False
    marketdata_approval_reference: str=''
    marketdata_allowed_segments: str='NSE_EQ,BSE_EQ,NSE_FO,BSE_FO,NSE_INDEX,BSE_INDEX'
    marketdata_allowed_modes: str='ltpc'
    marketdata_max_users: int=Field(default=1,ge=1,le=10000)
    marketdata_max_instruments: int=Field(default=1000,ge=1,le=1500)
    marketdata_per_user_limit: int=Field(default=50,ge=1,le=500)
    marketdata_stale_seconds: int=Field(default=15,ge=3,le=120)
    marketdata_cache_seconds: int=Field(default=300,ge=60,le=3600)
    marketdata_stream_maxlen: int=Field(default=10000,ge=100,le=100000)
    marketdata_tick_persist_seconds: int=Field(default=0,ge=0,le=3600)
    marketdata_tick_retention_hours: int=Field(default=24,ge=1,le=168)
    marketdata_worker_lease_seconds: int=Field(default=30,ge=15,le=120)
    marketdata_queue_size: int=Field(default=512,ge=16,le=4096)
    marketdata_candle_response_limit: int=Field(default=5000,ge=100,le=10000)
    marketdata_holidays: str=''
    marketdata_special_sessions: str='{}'

    @model_validator(mode='after')
    def valid_policy(self):
        if self.marketdata_distribution_approved and (not self.marketdata_approval_reference.strip() or self.marketdata_approval_reference.strip().lower() in ('false','true','pending')):
            raise ValueError('Distribution approval requires a verified written reference')
        if not set(self.marketdata_allowed_modes.split(',')) <= {'ltpc','full','option_greeks'}:
            raise ValueError('Unsupported configured feed mode')
        if self.marketdata_tick_persist_seconds and self.marketdata_tick_persist_seconds<60:
            raise ValueError('Tick persistence must be disabled or at least 60 seconds apart')
        if not self.segments or not self.segments <= {'NSE_EQ','BSE_EQ','NSE_FO','BSE_FO','NSE_INDEX','BSE_INDEX'}:
            raise ValueError('Unsupported configured exchange segment')
        import json
        from datetime import date,time
        for day in filter(None,self.marketdata_holidays.split(',')):date.fromisoformat(day)
        sessions=json.loads(self.marketdata_special_sessions)
        if not isinstance(sessions,dict):raise ValueError('Special sessions must be an object')
        for day,hours in sessions.items():
            date.fromisoformat(day)
            if not isinstance(hours,list) or len(hours)!=2 or time.fromisoformat(hours[0])>=time.fromisoformat(hours[1]):raise ValueError('Invalid special session hours')
        return self
    @property
    def segments(self): return set(self.marketdata_allowed_segments.split(','))
    @property
    def modes(self): return set(self.marketdata_allowed_modes.split(','))
market_settings=MarketSettings()
