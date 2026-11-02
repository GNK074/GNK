from alembic import op
from sqlalchemy import MetaData, Table, Column, String, Text, Boolean, DateTime, ForeignKey
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None
metadata = MetaData()
Table('users', metadata, Column('id',String(36),primary_key=True), Column('email',String(254),unique=True,index=True,nullable=False), Column('name',String(100),nullable=False), Column('password',Text,nullable=False), Column('verified',Boolean,nullable=False), Column('active',Boolean,nullable=False), Column('role',String(20),nullable=False), Column('created',DateTime(timezone=True),nullable=False))
Table('tokens',metadata,Column('id',String(64),primary_key=True),Column('user_id',ForeignKey('users.id'),index=True,nullable=False),Column('kind',String(20),nullable=False),Column('expires',DateTime(timezone=True),nullable=False),Column('used',Boolean,nullable=False))
Table('user_sessions',metadata,Column('id',String(36),primary_key=True),Column('user_id',ForeignKey('users.id'),index=True,nullable=False),Column('refresh_hash',String(64),unique=True,nullable=False),Column('csrf',String(64),nullable=False),Column('expires',DateTime(timezone=True),nullable=False),Column('revoked',Boolean,nullable=False),Column('agent',String(300),nullable=False),Column('created',DateTime(timezone=True),nullable=False))
Table('audit_logs',metadata,Column('id',String(36),primary_key=True),Column('user_id',String(36),index=True,nullable=True),Column('event',String(100),nullable=False),Column('created',DateTime(timezone=True),nullable=False))
def upgrade(): metadata.create_all(op.get_bind())
def downgrade(): metadata.drop_all(op.get_bind())
