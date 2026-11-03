"""Persistent tenant signals and historical order-intent backfill."""
from alembic import op
from sqlalchemy import Column,String,Integer,Numeric,DateTime,ForeignKey,ForeignKeyConstraint,UniqueConstraint,text,Table,MetaData
from datetime import datetime,timezone
import uuid
revision='0008'
down_revision='0007'
branch_labels=None
depends_on=None

def upgrade():
    with op.batch_alter_table('live_orders') as batch:
        batch.create_unique_constraint('uq_live_order_owner',['id','user_id'])
    op.create_table('trade_signals',
        Column('strategy_id',String(length=36),primary_key=False,nullable=False),
        Column('account_id',String(length=36),primary_key=False,nullable=True),
        Column('instrument_id',String(length=36),ForeignKey('market_instruments.id'),primary_key=False,nullable=False),
        Column('symbol',String(length=100),primary_key=False,nullable=False),
        Column('strike_price',Numeric(precision=24, scale=8),primary_key=False,nullable=True),
        Column('order_type',String(length=12),primary_key=False,nullable=False),
        Column('side',String(length=4),primary_key=False,nullable=False),
        Column('quantity',Integer(),primary_key=False,nullable=False),
        Column('reference_price',Numeric(precision=24, scale=8),primary_key=False,nullable=True),
        Column('signal_time',DateTime(timezone=True),primary_key=False,nullable=False),
        Column('source',String(length=24),primary_key=False,nullable=False),
        Column('source_order_id',String(length=36),primary_key=False,nullable=True),
        Column('note',String(length=500),primary_key=False,nullable=False),
        Column('id',String(length=36),primary_key=True,nullable=False),
        Column('user_id',String(length=36),ForeignKey('users.id'),primary_key=False,nullable=False),
        Column('created_at',DateTime(timezone=True),primary_key=False,nullable=False),
        ForeignKeyConstraint(['account_id', 'user_id'],['broker_accounts.id', 'broker_accounts.user_id']),
        ForeignKeyConstraint(['strategy_id', 'user_id'],['strategies.id', 'strategies.user_id']),
        UniqueConstraint(*['source_order_id']),
        ForeignKeyConstraint(['source_order_id','user_id'],['live_orders.id','live_orders.user_id']),
    )
    op.create_index('ix_trade_signals_user_id','trade_signals',['user_id'])
    op.create_index('ix_trade_signals_signal_time','trade_signals',['signal_time'])
    connection=op.get_bind()
    table=Table('trade_signals',MetaData(),autoload_with=connection)
    source=connection.execute(text("SELECT o.id,o.user_id,o.strategy_id,o.account_id,o.instrument_id,o.symbol,o.side,o.quantity,o.price,o.created_at,m.strike FROM live_orders o LEFT JOIN market_instruments m ON m.id=o.instrument_id"))
    while True:
        batch=source.mappings().fetchmany(500)
        if not batch:break
        values=[]
        for row in batch:
            stamp=row['created_at']
            if isinstance(stamp,str):stamp=datetime.fromisoformat(stamp)
            if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
            values.append(dict(id=str(uuid.uuid4()),user_id=row['user_id'],strategy_id=row['strategy_id'],account_id=row['account_id'],instrument_id=row['instrument_id'],symbol=row['symbol'],strike_price=row['strike'],order_type='LIMIT',side=row['side'],quantity=row['quantity'],reference_price=row['price'],signal_time=stamp,source='ORDER_REQUEST',source_order_id=row['id'],note='Historical user-submitted order request; not a broker fill.',created_at=datetime.now(timezone.utc)))
        connection.execute(table.insert(),values)
    if connection.dialect.name=='postgresql':
        op.execute('ALTER TABLE trade_signals ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE trade_signals FORCE ROW LEVEL SECURITY')
        op.execute("CREATE POLICY tenant_owner ON trade_signals USING (user_id=nullif(current_setting('app.user_id',true),'')) WITH CHECK (user_id=nullif(current_setting('app.user_id',true),''))")


def downgrade():
    raise RuntimeError('Preserve signal history; use a reviewed forward migration.')
