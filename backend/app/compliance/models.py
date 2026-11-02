from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database.session import Base
from app.core.config import ident, now

class DisclosureAcknowledgment(Base):
    __tablename__ = 'disclosure_acknowledgments'
    __table_args__ = (UniqueConstraint('user_id', 'session_id', 'disclosure_id', 'disclosure_version', 'period_key', name='uq_disclosure_receipt'), Index('ix_disclosure_owner_session', 'user_id', 'session_id'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=ident)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('user_sessions.id'))
    disclosure_id: Mapped[str] = mapped_column(String(60))
    disclosure_version: Mapped[str] = mapped_column(String(100))
    content_sha256: Mapped[str] = mapped_column(String(64))
    period_key: Mapped[str] = mapped_column(String(32))
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
