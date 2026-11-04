"""Owned read-only broker snapshots; no execution records are modified."""
from datetime import datetime
from sqlalchemy import String,DateTime,JSON,ForeignKeyConstraint,UniqueConstraint,Text,Integer
from sqlalchemy.orm import Mapped,mapped_column
from app.database.session import Base
from app.models.trading import Owned

class PortfolioSnapshot(Owned,Base):
    __tablename__='portfolio_snapshots'
    __table_args__=(ForeignKeyConstraint(['account_id','user_id'],['broker_accounts.id','broker_accounts.user_id']),UniqueConstraint('account_id','kind'))
    account_id:Mapped[str]=mapped_column(String(36),index=True)
    kind:Mapped[str]=mapped_column(String(16))
    rows:Mapped[list]=mapped_column(JSON,default=list)
    fetched_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    credential_version:Mapped[str]=mapped_column(String(64))

class PortfolioSync(Owned,Base):
    __tablename__='portfolio_sync_states'
    __table_args__=(ForeignKeyConstraint(['account_id','user_id'],['broker_accounts.id','broker_accounts.user_id']),UniqueConstraint('account_id'))
    account_id:Mapped[str]=mapped_column(String(36),index=True)
    state:Mapped[str]=mapped_column(String(24),default='QUEUED')
    requested_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    attempted_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    next_attempt_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    failures:Mapped[int]=mapped_column(Integer,default=0)
    errors:Mapped[dict]=mapped_column(JSON,default=dict)
