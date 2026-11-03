"""Durable live order intents are separate from paper orders and positions."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String,Integer,Numeric,DateTime,JSON,ForeignKeyConstraint,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.database.session import Base
from app.models.trading import Owned
from app.core.config import now
class LiveOrder(Owned,Base):
    __tablename__='live_orders'
    __table_args__=(UniqueConstraint('user_id','idempotency_key'),UniqueConstraint('account_id','provider_order_id'),ForeignKeyConstraint(['account_id','user_id'],['broker_accounts.id','broker_accounts.user_id']),ForeignKeyConstraint(['strategy_id','user_id'],['strategies.id','strategies.user_id']))
    account_id:Mapped[str]=mapped_column(String(36))
    strategy_id:Mapped[str]=mapped_column(String(36))
    instrument_id:Mapped[str]=mapped_column(String(36))
    instrument_key:Mapped[str]=mapped_column(String(200))
    symbol:Mapped[str]=mapped_column(String(100))
    side:Mapped[str]=mapped_column(String(4))
    quantity:Mapped[int]=mapped_column(Integer)
    price:Mapped[Decimal]=mapped_column(Numeric(24,8))
    product:Mapped[str]=mapped_column(String(4),default='I')
    status:Mapped[str]=mapped_column(String(30),default='SUBMITTING')
    provider_order_id:Mapped[str|None]=mapped_column(String(100),nullable=True)
    tag:Mapped[str]=mapped_column(String(40),unique=True)
    idempotency_key:Mapped[str]=mapped_column(String(80))
    request_hash:Mapped[str]=mapped_column(String(64))
    filled_quantity:Mapped[int]=mapped_column(Integer,default=0)
    average_price:Mapped[Decimal|None]=mapped_column(Numeric(24,8),nullable=True)
    fills:Mapped[list]=mapped_column(JSON,default=list)
    error_code:Mapped[str|None]=mapped_column(String(80),nullable=True)
    reconciled_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
