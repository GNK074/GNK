"""Market-data engine metadata and isolated user subscriptions."""
from alembic import op
from sqlalchemy import String,Text,Boolean,Integer,Date,DateTime,Numeric,JSON,ForeignKey,Column,UniqueConstraint
revision='0006'
down_revision='0005'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('market_data_provider_secrets',
        Column('provider',String(length=20),primary_key=True,nullable=False),
        Column('ciphertext',Text(),primary_key=False,nullable=False),
        Column('key_version',String(length=30),primary_key=False,nullable=False),
        Column('updated',DateTime(timezone=True),primary_key=False,nullable=False),
    )
    op.create_table('market_data_provider_status',
        Column('provider',String(length=20),primary_key=True,nullable=False),
        Column('enabled',Boolean(),primary_key=False,nullable=False),
        Column('state',String(length=30),primary_key=False,nullable=False),
        Column('last_message_at',DateTime(timezone=True),primary_key=False,nullable=True),
        Column('error_code',String(length=80),primary_key=False,nullable=True),
        Column('updated',DateTime(timezone=True),primary_key=False,nullable=False),
    )
    op.create_table('market_instruments',
        Column('id',String(length=36),primary_key=True,nullable=False),
        Column('provider',String(length=20),primary_key=False,nullable=False),
        Column('instrument_key',String(length=200),primary_key=False,nullable=False),
        Column('exchange',String(length=8),primary_key=False,nullable=False),
        Column('segment',String(length=30),primary_key=False,nullable=False),
        Column('symbol',String(length=100),primary_key=False,nullable=False),
        Column('name',String(length=250),primary_key=False,nullable=False),
        Column('instrument_type',String(length=30),primary_key=False,nullable=False),
        Column('expiry',Date(),primary_key=False,nullable=True),
        Column('strike',Numeric(precision=24, scale=8),primary_key=False,nullable=True),
        Column('lot_size',Integer(),primary_key=False,nullable=True),
        Column('tick_size',Numeric(precision=24, scale=8),primary_key=False,nullable=True),
        Column('underlying',String(length=150),primary_key=False,nullable=True),
        Column('status',String(length=24),primary_key=False,nullable=False),
        Column('version',String(length=64),primary_key=False,nullable=False),
        Column('synced_at',DateTime(timezone=True),primary_key=False,nullable=False),
        UniqueConstraint('instrument_key',name=None),
    )
    op.create_index('ix_market_instruments_segment','market_instruments',['segment'],unique=False)
    op.create_index('ix_market_instruments_symbol','market_instruments',['symbol'],unique=False)
    op.create_index('ix_market_instruments_exchange','market_instruments',['exchange'],unique=False)
    op.create_index('ix_market_instruments_status','market_instruments',['status'],unique=False)
    op.create_index('ix_market_instruments_instrument_type','market_instruments',['instrument_type'],unique=False)
    op.create_index('ix_market_instruments_expiry','market_instruments',['expiry'],unique=False)
    op.create_table('market_candles',
        Column('id',String(length=36),primary_key=True,nullable=False),
        Column('instrument_id',String(length=36),ForeignKey('market_instruments.id'),primary_key=False,nullable=False),
        Column('exchange',String(length=8),primary_key=False,nullable=False),
        Column('timestamp',DateTime(timezone=True),primary_key=False,nullable=False),
        Column('exchange_timestamp',String(length=50),primary_key=False,nullable=False),
        Column('open',Numeric(precision=24, scale=8),primary_key=False,nullable=False),
        Column('high',Numeric(precision=24, scale=8),primary_key=False,nullable=False),
        Column('low',Numeric(precision=24, scale=8),primary_key=False,nullable=False),
        Column('close',Numeric(precision=24, scale=8),primary_key=False,nullable=False),
        Column('volume',Numeric(precision=28, scale=0),primary_key=False,nullable=True),
        Column('oi',Numeric(precision=28, scale=4),primary_key=False,nullable=True),
        Column('interval',String(length=15),primary_key=False,nullable=False),
        Column('provider',String(length=20),primary_key=False,nullable=False),
        Column('source',String(length=30),primary_key=False,nullable=False),
        Column('quality',String(length=20),primary_key=False,nullable=False),
        UniqueConstraint('instrument_id','provider','interval','timestamp',name='uq_market_candle'),
    )
    op.create_index('ix_market_candle_lookup','market_candles',['instrument_id', 'interval', 'timestamp'],unique=False)
    op.create_table('market_data_entitlements',
        Column('user_id',String(length=36),ForeignKey('users.id'),primary_key=True,nullable=False),
        Column('enabled',Boolean(),primary_key=False,nullable=False),
        Column('segments',JSON(),primary_key=False,nullable=False),
        Column('modes',JSON(),primary_key=False,nullable=False),
        Column('max_instruments',Integer(),primary_key=False,nullable=False),
        Column('expires_at',DateTime(timezone=True),primary_key=False,nullable=True),
    )
    op.create_table('market_data_subscriptions',
        Column('id',String(length=36),primary_key=True,nullable=False),
        Column('user_id',String(length=36),ForeignKey('users.id'),primary_key=False,nullable=False),
        Column('instrument_key',String(length=200),ForeignKey('market_instruments.instrument_key'),primary_key=False,nullable=False),
        Column('mode',String(length=20),primary_key=False,nullable=False),
        Column('created',DateTime(timezone=True),primary_key=False,nullable=False),
        UniqueConstraint('user_id','instrument_key',name='uq_market_subscription'),
    )
    op.create_index('ix_market_data_subscriptions_instrument_key','market_data_subscriptions',['instrument_key'],unique=False)
    op.create_index('ix_market_data_subscriptions_user_id','market_data_subscriptions',['user_id'],unique=False)
    op.create_table('market_data_sync_jobs',
        Column('id',String(length=36),primary_key=True,nullable=False),
        Column('requested_by',String(length=36),ForeignKey('users.id'),primary_key=False,nullable=True),
        Column('kind',String(length=20),primary_key=False,nullable=False),
        Column('state',String(length=20),primary_key=False,nullable=False),
        Column('dedup_key',String(length=64),primary_key=False,nullable=False),
        Column('parameters',JSON(),primary_key=False,nullable=False),
        Column('processed',Integer(),primary_key=False,nullable=False),
        Column('error_code',String(length=80),primary_key=False,nullable=True),
        Column('created',DateTime(timezone=True),primary_key=False,nullable=False),
        Column('started',DateTime(timezone=True),primary_key=False,nullable=True),
        Column('finished',DateTime(timezone=True),primary_key=False,nullable=True),
    )
    op.create_index('ix_market_data_sync_jobs_kind','market_data_sync_jobs',['kind'],unique=False)
    op.create_index('ix_market_data_sync_jobs_dedup_key','market_data_sync_jobs',['dedup_key'],unique=False)
    op.create_index('ix_market_data_sync_jobs_state','market_data_sync_jobs',['state'],unique=False)
    op.create_table('market_ticks_latest',
        Column('instrument_key',String(length=200),ForeignKey('market_instruments.instrument_key'),primary_key=True,nullable=False),
        Column('payload',JSON(),primary_key=False,nullable=False),
        Column('received_at',DateTime(timezone=True),primary_key=False,nullable=False),
        Column('expires_at',DateTime(timezone=True),primary_key=False,nullable=False),
    )
    op.create_index('ix_market_ticks_latest_expires_at','market_ticks_latest',['expires_at'],unique=False)
    if op.get_bind().dialect.name=='postgresql':
        owner="user_id = nullif(current_setting('app.user_id',true),'')"
        worker="current_setting('app.market_worker',true) = 'true'"
        admin="EXISTS (SELECT 1 FROM users u WHERE u.id=nullif(current_setting('app.user_id',true),'') AND u.role='SUPER_ADMIN' AND u.active AND u.verified)"
        for name,predicate in [('market_data_subscriptions',f'({owner} OR {worker})'),('market_data_entitlements',f'({owner} OR {worker} OR {admin})')]:
            op.execute(f'ALTER TABLE {name} ENABLE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE {name} FORCE ROW LEVEL SECURITY')
            op.execute(f'CREATE POLICY tenant_owner ON {name} USING ({predicate}) WITH CHECK ({predicate})')

def downgrade():
    raise RuntimeError('Preserve market-data and synchronization history. Use a reviewed forward migration.')
