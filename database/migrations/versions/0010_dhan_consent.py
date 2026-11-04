"""One-time owner/session-bound encrypted broker consent attempts."""
from alembic import op
import sqlalchemy as sa
revision='0010'
down_revision='0009'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('dhan_consent_attempts',sa.Column('id',sa.String(36),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('account_id',sa.String(36),nullable=False),sa.Column('session_id',sa.String(36),sa.ForeignKey('user_sessions.id'),nullable=False),sa.Column('state_hash',sa.String(64),unique=True,nullable=False),sa.Column('secret_ciphertext',sa.Text(),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('consumed',sa.Boolean(),nullable=False),sa.ForeignKeyConstraint(['account_id','user_id'],['broker_accounts.id','broker_accounts.user_id']))
    op.create_index('ix_dhan_consent_attempts_user_id','dhan_consent_attempts',['user_id'])
    if op.get_bind().dialect.name=='postgresql':
        op.execute('ALTER TABLE dhan_consent_attempts ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE dhan_consent_attempts FORCE ROW LEVEL SECURITY')
        op.execute("CREATE POLICY tenant_owner ON dhan_consent_attempts USING (user_id=nullif(current_setting('app.user_id',true),'')) WITH CHECK (user_id=nullif(current_setting('app.user_id',true),''))")
def downgrade():raise RuntimeError('Preserve consent audit state; use a reviewed forward migration.')
