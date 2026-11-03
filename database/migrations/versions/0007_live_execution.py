"""Isolated durable live execution intents."""
from alembic import op
from sqlalchemy import Column,String,Integer,Numeric,DateTime,JSON,ForeignKey,ForeignKeyConstraint,UniqueConstraint
revision='0007'
down_revision='0006'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('live_orders',
        Column('account_id',String(length=36),primary_key=False,nullable=False),
        Column('strategy_id',String(length=36),primary_key=False,nullable=False),
        Column('instrument_id',String(length=36),primary_key=False,nullable=False),
        Column('instrument_key',String(length=200),primary_key=False,nullable=False),
        Column('symbol',String(length=100),primary_key=False,nullable=False),
        Column('side',String(length=4),primary_key=False,nullable=False),
        Column('quantity',Integer(),primary_key=False,nullable=False),
        Column('price',Numeric(precision=24, scale=8),primary_key=False,nullable=False),
        Column('product',String(length=4),primary_key=False,nullable=False),
        Column('status',String(length=30),primary_key=False,nullable=False),
        Column('provider_order_id',String(length=100),primary_key=False,nullable=True),
        Column('tag',String(length=40),primary_key=False,nullable=False),
        Column('idempotency_key',String(length=80),primary_key=False,nullable=False),
        Column('request_hash',String(length=64),primary_key=False,nullable=False),
        Column('filled_quantity',Integer(),primary_key=False,nullable=False),
        Column('average_price',Numeric(precision=24, scale=8),primary_key=False,nullable=True),
        Column('fills',JSON(),primary_key=False,nullable=False),
        Column('error_code',String(length=80),primary_key=False,nullable=True),
        Column('reconciled_at',DateTime(timezone=True),primary_key=False,nullable=True),
        Column('updated_at',DateTime(timezone=True),primary_key=False,nullable=False),
        Column('id',String(length=36),primary_key=True,nullable=False),
        Column('user_id',String(length=36),ForeignKey('users.id'),primary_key=False,nullable=False),
        Column('created_at',DateTime(timezone=True),primary_key=False,nullable=False),
        ForeignKeyConstraint(['strategy_id', 'user_id'],['strategies.id', 'strategies.user_id']),
        ForeignKeyConstraint(['account_id', 'user_id'],['broker_accounts.id', 'broker_accounts.user_id']),
        UniqueConstraint(*['tag']),
        UniqueConstraint(*['user_id', 'idempotency_key']),
        UniqueConstraint(*['account_id', 'provider_order_id']),
    )
    op.create_index('ix_live_orders_user_id','live_orders',['user_id'])
    if op.get_bind().dialect.name=='postgresql':
        op.execute('ALTER TABLE live_orders ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE live_orders FORCE ROW LEVEL SECURITY')
        op.execute("CREATE POLICY tenant_owner ON live_orders USING (user_id=nullif(current_setting('app.user_id',true),'')) WITH CHECK (user_id=nullif(current_setting('app.user_id',true),''))")

def downgrade():
    raise RuntimeError('Preserve broker order history; use a reviewed forward migration.')
