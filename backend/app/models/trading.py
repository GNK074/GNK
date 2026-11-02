from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint, ForeignKeyConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database.session import Base
from app.core.config import ident, now

class Owned:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=ident)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class BrokerIntegration(Base):
    __tablename__ = 'broker_integrations'
    broker: Mapped[str] = mapped_column(String(30), primary_key=True)
    mode: Mapped[str] = mapped_column(String(20), default='DISABLED')
    auth_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    client_id: Mapped[str] = mapped_column(Text, default='')
    encrypted_client_secret: Mapped[str] = mapped_column(Text, default='')
    redirect_uri: Mapped[str] = mapped_column(Text, default='')

class BrokerAccount(Owned, Base):
    __tablename__ = 'broker_accounts'
    __table_args__ = (UniqueConstraint('id', 'user_id'), UniqueConstraint('broker', 'account_identifier'))
    broker: Mapped[str] = mapped_column(String(30))
    account_identifier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default='pending')
    live_authorized: Mapped[bool] = mapped_column(Boolean, default=False)
    kill_switch: Mapped[bool] = mapped_column(Boolean, default=True)

class BrokerCredential(Owned, Base):
    __tablename__ = 'broker_credentials'
    __table_args__ = (ForeignKeyConstraint(['account_id', 'user_id'], ['broker_accounts.id', 'broker_accounts.user_id']),)
    account_id: Mapped[str] = mapped_column(String(36), unique=True)
    ciphertext: Mapped[str] = mapped_column(Text)
    key_version: Mapped[str] = mapped_column(String(30))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class BrokerAuthState(Owned, Base):
    __tablename__ = 'broker_auth_states'
    __table_args__ = (ForeignKeyConstraint(['account_id', 'user_id'], ['broker_accounts.id', 'broker_accounts.user_id']),)
    account_id: Mapped[str] = mapped_column(String(36))
    broker: Mapped[str] = mapped_column(String(30))
    state_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)

class Strategy(Owned, Base):
    __tablename__ = 'strategies'
    __table_args__ = (UniqueConstraint('id', 'user_id'),)
    name: Mapped[str] = mapped_column(String(100))
    approved: Mapped[bool] = mapped_column(Boolean, default=False)

class RiskConfiguration(Owned, Base):
    __tablename__ = 'risk_configurations'
    __table_args__ = (UniqueConstraint('user_id'),)
    max_quantity: Mapped[int] = mapped_column(Integer, default=100)
    max_order_value: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=100000)
    max_daily_orders: Mapped[int] = mapped_column(Integer, default=50)
    max_daily_loss: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=5000)
    max_positions: Mapped[int] = mapped_column(Integer, default=3)
    kill_switch: Mapped[bool] = mapped_column(Boolean, default=False)

class Order(Owned, Base):
    __tablename__ = 'orders'
    __table_args__ = (UniqueConstraint('user_id', 'idempotency_key'), ForeignKeyConstraint(['strategy_id', 'user_id'], ['strategies.id', 'strategies.user_id']))
    strategy_id: Mapped[str] = mapped_column(String(36))
    symbol: Mapped[str] = mapped_column(String(40))
    side: Mapped[str] = mapped_column(String(4))
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    mode: Mapped[str] = mapped_column(String(10), default='paper')
    status: Mapped[str] = mapped_column(String(20), default='filled')
    idempotency_key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=0)

class Position(Owned, Base):
    __tablename__ = 'positions'
    __table_args__ = (UniqueConstraint('user_id', 'symbol'),)
    symbol: Mapped[str] = mapped_column(String(40))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    average_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=0)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 4), default=0)

class PlatformControl(Base):
    __tablename__ = 'platform_controls'
    id: Mapped[str] = mapped_column(String(20), primary_key=True, default='global')
    kill_switch: Mapped[bool] = mapped_column(Boolean, default=True)

class ApprovalRequest(Base):
    __tablename__ = 'broker_approval_requests'
    broker: Mapped[str] = mapped_column(String(30), primary_key=True)
    requested_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ApprovalRequirement(Base):
    __tablename__ = 'broker_approval_requirements'
    __table_args__ = (UniqueConstraint('broker', 'requirement'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=ident)
    broker: Mapped[str] = mapped_column(ForeignKey('broker_approval_requests.broker'), index=True)
    requirement: Mapped[int] = mapped_column(Integer)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)

class ApprovalEvidence(Base):
    __tablename__ = 'broker_approval_evidence'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=ident)
    requirement_id: Mapped[str] = mapped_column(ForeignKey('broker_approval_requirements.id'), index=True)
    reference: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    verified_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ApprovalHistory(Base):
    __tablename__ = 'broker_approval_history'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=ident)
    broker: Mapped[str] = mapped_column(String(30), index=True)
    actor: Mapped[str] = mapped_column(ForeignKey('users.id'))
    event: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ProductionStatus(Base):
    __tablename__ = 'broker_production_status'
    broker: Mapped[str] = mapped_column(String(30), primary_key=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
