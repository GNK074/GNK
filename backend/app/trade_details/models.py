"""Tenant-owned signal records. Signals do not submit broker orders."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String,DateTime,Numeric,Integer,ForeignKey,ForeignKeyConstraint,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.database.session import Base
from app.models.trading import Owned
from app.core.config import now
class TradeSignal(Owned,Base):
    __tablename__='trade_signals'
    __table_args__=(ForeignKeyConstraint(['source_order_id','user_id'],['live_orders.id','live_orders.user_id']),ForeignKeyConstraint(['strategy_id','user_id'],['strategies.id','strategies.user_id']),ForeignKeyConstraint(['account_id','user_id'],['broker_accounts.id','broker_accounts.user_id']),)
    strategy_id:Mapped[str]=mapped_column(String(36))
    account_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    instrument_id:Mapped[str]=mapped_column(ForeignKey('market_instruments.id'))
    symbol:Mapped[str]=mapped_column(String(100))
    strike_price:Mapped[Decimal|None]=mapped_column(Numeric(24,8),nullable=True)
    order_type:Mapped[str]=mapped_column(String(12),default='LIMIT')
    side:Mapped[str]=mapped_column(String(4))
    quantity:Mapped[int]=mapped_column(Integer)
    reference_price:Mapped[Decimal|None]=mapped_column(Numeric(24,8),nullable=True)
    signal_time:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)
    source:Mapped[str]=mapped_column(String(24),default='MANUAL')
    source_order_id:Mapped[str|None]=mapped_column(String(36),nullable=True,unique=True)
    note:Mapped[str]=mapped_column(String(500),default='')
