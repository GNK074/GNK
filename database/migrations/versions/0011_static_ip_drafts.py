"""Owner-scoped static IP registration drafts."""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'static_ip_drafts',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('broker', sa.String(16), nullable=False),
        sa.Column('primary_ip', sa.String(15), nullable=False),
        sa.Column('secondary_ip', sa.String(15)),
        sa.Column('status', sa.String(20), nullable=False, server_default='DRAFT'),
        sa.Column('submitted_week', sa.Date()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE static_ip_drafts ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE static_ip_drafts FORCE ROW LEVEL SECURITY')
        op.execute("CREATE POLICY tenant_owner ON static_ip_drafts USING (user_id=nullif(current_setting('app.user_id',true),'')) WITH CHECK (user_id=nullif(current_setting('app.user_id',true),''))")


def downgrade():
    raise RuntimeError('Preserve registration drafts through a reviewed forward migration.')
