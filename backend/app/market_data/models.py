from datetime import date,datetime
from sqlalchemy import String,Text,Boolean,Integer,Date,DateTime,Numeric,JSON,ForeignKey,UniqueConstraint,Index
from sqlalchemy.orm import Mapped,mapped_column
from app.database.session import Base
from app.core.config import now,ident

class MarketInstrument(Base):
    __tablename__='market_instruments'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=ident)
    provider: Mapped[str]=mapped_column(String(20),default='upstox')
    instrument_key: Mapped[str]=mapped_column(String(200),unique=True)
    exchange: Mapped[str]=mapped_column(String(8),index=True)
    segment: Mapped[str]=mapped_column(String(30),index=True)
    symbol: Mapped[str]=mapped_column(String(100),index=True)
    name: Mapped[str]=mapped_column(String(250))
    instrument_type: Mapped[str]=mapped_column(String(30),index=True)
    expiry: Mapped[date|None]=mapped_column(Date,nullable=True,index=True)
    strike: Mapped[float|None]=mapped_column(Numeric(24,8),nullable=True)
    lot_size: Mapped[int|None]=mapped_column(Integer,nullable=True)
    tick_size: Mapped[float|None]=mapped_column(Numeric(24,8),nullable=True)
    underlying: Mapped[str|None]=mapped_column(String(150),nullable=True)
    status: Mapped[str]=mapped_column(String(24),default='ACTIVE',index=True)
    version: Mapped[str]=mapped_column(String(64))
    synced_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class MarketTickLatest(Base):
    __tablename__='market_ticks_latest'
    instrument_key: Mapped[str]=mapped_column(ForeignKey('market_instruments.instrument_key'),primary_key=True)
    payload: Mapped[dict]=mapped_column(JSON)
    received_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)

class MarketCandle(Base):
    __tablename__='market_candles'
    __table_args__=(UniqueConstraint('instrument_id','provider','interval','timestamp',name='uq_market_candle'),Index('ix_market_candle_lookup','instrument_id','interval','timestamp'))
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=ident)
    instrument_id: Mapped[str]=mapped_column(ForeignKey('market_instruments.id'))
    exchange: Mapped[str]=mapped_column(String(8))
    timestamp: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    exchange_timestamp: Mapped[str]=mapped_column(String(50))
    open: Mapped[float]=mapped_column(Numeric(24,8))
    high: Mapped[float]=mapped_column(Numeric(24,8))
    low: Mapped[float]=mapped_column(Numeric(24,8))
    close: Mapped[float]=mapped_column(Numeric(24,8))
    volume: Mapped[int|None]=mapped_column(Numeric(28,0),nullable=True)
    oi: Mapped[float|None]=mapped_column(Numeric(28,4),nullable=True)
    interval: Mapped[str]=mapped_column(String(15))
    provider: Mapped[str]=mapped_column(String(20),default='upstox')
    source: Mapped[str]=mapped_column(String(30),default='UPSTOX_V3')
    quality: Mapped[str]=mapped_column(String(20),default='VALIDATED')

class MarketSyncJob(Base):
    __tablename__='market_data_sync_jobs'
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=ident)
    requested_by: Mapped[str|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    kind: Mapped[str]=mapped_column(String(20),index=True)
    state: Mapped[str]=mapped_column(String(20),default='QUEUED',index=True)
    dedup_key: Mapped[str]=mapped_column(String(64),index=True)
    parameters: Mapped[dict]=mapped_column(JSON,default=dict)
    processed: Mapped[int]=mapped_column(Integer,default=0)
    error_code: Mapped[str|None]=mapped_column(String(80),nullable=True)
    created: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    started: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    finished: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class MarketProviderStatus(Base):
    __tablename__='market_data_provider_status'
    provider: Mapped[str]=mapped_column(String(20),primary_key=True)
    enabled: Mapped[bool]=mapped_column(Boolean,default=False)
    state: Mapped[str]=mapped_column(String(30),default='DISABLED')
    last_message_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    error_code: Mapped[str|None]=mapped_column(String(80),nullable=True)
    updated: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class MarketProviderSecret(Base):
    __tablename__='market_data_provider_secrets'
    provider: Mapped[str]=mapped_column(String(20),primary_key=True)
    ciphertext: Mapped[str]=mapped_column(Text)
    key_version: Mapped[str]=mapped_column(String(30))
    updated: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class MarketEntitlement(Base):
    __tablename__='market_data_entitlements'
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id'),primary_key=True)
    enabled: Mapped[bool]=mapped_column(Boolean,default=False)
    segments: Mapped[list]=mapped_column(JSON,default=list)
    modes: Mapped[list]=mapped_column(JSON,default=list)
    max_instruments: Mapped[int]=mapped_column(Integer,default=50)
    expires_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class MarketSubscription(Base):
    __tablename__='market_data_subscriptions'
    __table_args__=(UniqueConstraint('user_id','instrument_key',name='uq_market_subscription'),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=ident)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    instrument_key: Mapped[str]=mapped_column(ForeignKey('market_instruments.instrument_key'),index=True)
    mode: Mapped[str]=mapped_column(String(20),default='ltpc')
    created: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
