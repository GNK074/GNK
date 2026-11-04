"""Tenant-owned latest broker snapshots and sync state. No trading flag changes."""
from alembic import op
import sqlalchemy as sa
revision='0009'
down_revision='0008'
branch_labels=None
depends_on=None

def ownership():
    return [sa.Column('id',sa.String(36),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('account_id',sa.String(36),nullable=False),sa.ForeignKeyConstraint(['account_id','user_id'],['broker_accounts.id','broker_accounts.user_id'])]

def upgrade():
    op.create_table('portfolio_snapshots',*ownership(),sa.Column('kind',sa.String(16),nullable=False),sa.Column('rows',sa.JSON(),nullable=False),sa.Column('fetched_at',sa.DateTime(timezone=True),nullable=False),sa.Column('credential_version',sa.String(64),nullable=False),sa.UniqueConstraint('account_id','kind'))
    op.create_table('portfolio_sync_states',*ownership(),sa.Column('state',sa.String(24),nullable=False),sa.Column('requested_at',sa.DateTime(timezone=True)),sa.Column('attempted_at',sa.DateTime(timezone=True)),sa.Column('completed_at',sa.DateTime(timezone=True)),sa.Column('next_attempt_at',sa.DateTime(timezone=True)),sa.Column('failures',sa.Integer(),nullable=False),sa.Column('errors',sa.JSON(),nullable=False),sa.UniqueConstraint('account_id'))
    for table in ('portfolio_snapshots','portfolio_sync_states'):
        op.create_index('ix_'+table+'_user_id',table,['user_id'])
        op.create_index('ix_'+table+'_account_id',table,['account_id'])
        if op.get_bind().dialect.name=='postgresql':
            op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
            op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
            op.execute(f"CREATE POLICY tenant_owner ON {table} USING (user_id=nullif(current_setting('app.user_id',true),'')) WITH CHECK (user_id=nullif(current_setting('app.user_id',true),''))")

def downgrade():
    raise RuntimeError('Retain portfolio snapshots; use a reviewed forward migration.')
