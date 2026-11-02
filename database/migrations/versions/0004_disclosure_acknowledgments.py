"""Owner-scoped, per-login risk disclosure receipts."""
from alembic import op
import sqlalchemy as sa
revision='0004'
down_revision='0003'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('disclosure_acknowledgments',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('session_id',sa.String(36),sa.ForeignKey('user_sessions.id'),nullable=False),
        sa.Column('disclosure_id',sa.String(60),nullable=False),
        sa.Column('disclosure_version',sa.String(100),nullable=False),
        sa.Column('content_sha256',sa.String(64),nullable=False),
        sa.Column('period_key',sa.String(32),nullable=False),
        sa.Column('acknowledged_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('user_id','session_id','disclosure_id','disclosure_version','period_key',name='uq_disclosure_receipt'))
    op.create_index('ix_disclosure_acknowledgments_user_id','disclosure_acknowledgments',['user_id'])
    op.create_index('ix_disclosure_owner_session','disclosure_acknowledgments',['user_id','session_id'])
    if op.get_bind().dialect.name=='postgresql':
        predicate="user_id = nullif(current_setting('app.user_id',true),'')"
        op.execute('ALTER TABLE disclosure_acknowledgments ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE disclosure_acknowledgments FORCE ROW LEVEL SECURITY')
        op.execute(f'CREATE POLICY tenant_read ON disclosure_acknowledgments FOR SELECT USING ({predicate})')
        session_owner = 'EXISTS (SELECT 1 FROM user_sessions us WHERE us.id = disclosure_acknowledgments.session_id AND us.user_id = disclosure_acknowledgments.user_id)'
        op.execute(f'CREATE POLICY tenant_insert ON disclosure_acknowledgments FOR INSERT WITH CHECK ({predicate} AND {session_owner})')
        # No UPDATE or DELETE policies: runtime receipts are append-only.


def downgrade():
    raise RuntimeError('Preserve disclosure audit history. Use a reviewed forward migration.')
