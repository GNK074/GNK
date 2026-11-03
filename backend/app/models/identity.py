from datetime import datetime, date
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, BigInteger, Date, LargeBinary, Integer, false
from sqlalchemy.orm import Mapped, mapped_column
from app.core.config import ident, now
from app.database.session import Base

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=ident)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    gender: Mapped[str | None] = mapped_column(String(30), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(20), nullable=True)
    theme: Mapped[str] = mapped_column(String(20), default='carbon_black', server_default='carbon_black')
    avatar_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    avatar_version: Mapped[int] = mapped_column(Integer, default=0, server_default='0')
    password: Mapped[str] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[str] = mapped_column(String(20), default='USER')
    mfa_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_reenroll_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    mfa_counter: Mapped[int] = mapped_column(BigInteger, default=-1)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Token(Base):
    __tablename__ = 'tokens'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    target_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)

class LoginSession(Base):
    __tablename__ = 'user_sessions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=ident)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    refresh_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_complete: Mapped[bool] = mapped_column(Boolean, default=True)
    agent: Mapped[str] = mapped_column(String(300))
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Audit(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=ident)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event: Mapped[str] = mapped_column(String(100))
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MfaRecoveryCode(Base):
    __tablename__ = 'mfa_recovery_codes'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=ident)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class MfaRecoveryRequest(Base):
    __tablename__ = 'mfa_recovery_requests'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=ident)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    email_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    email_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    backup_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
