from datetime import datetime
from sqlalchemy import String,DateTime,Boolean,Text,ForeignKey,ForeignKeyConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.database.session import Base
from app.models.trading import Owned
class ConsentAttempt(Owned,Base):
    __tablename__='dhan_consent_attempts'
    __table_args__=(ForeignKeyConstraint(['account_id','user_id'],['broker_accounts.id','broker_accounts.user_id']),)
    account_id:Mapped[str]=mapped_column(String(36))
    session_id:Mapped[str]=mapped_column(ForeignKey('user_sessions.id'))
    state_hash:Mapped[str]=mapped_column(String(64),unique=True)
    secret_ciphertext:Mapped[str]=mapped_column(Text)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    consumed:Mapped[bool]=mapped_column(Boolean,default=False)
