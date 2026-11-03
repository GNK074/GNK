"""Hashed MFA recovery codes and reviewed recovery requests."""
from alembic import op
import sqlalchemy as sa
revision='0005'
down_revision='0004'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('users',sa.Column('mfa_reenroll_required',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.create_table('mfa_recovery_codes',sa.Column('id',sa.String(36),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('code_hash',sa.String(64),nullable=False,unique=True),sa.Column('used',sa.Boolean(),nullable=False),sa.Column('created',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_mfa_recovery_codes_user_id','mfa_recovery_codes',['user_id'])
    op.create_table('mfa_recovery_requests',sa.Column('id',sa.String(36),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('email_token_hash',sa.String(64),nullable=False,unique=True),sa.Column('email_confirmed',sa.Boolean(),nullable=False),sa.Column('backup_verified',sa.Boolean(),nullable=False),sa.Column('consumed',sa.Boolean(),nullable=False),sa.Column('approved_by',sa.String(36),sa.ForeignKey('users.id')),sa.Column('expires',sa.DateTime(timezone=True),nullable=False),sa.Column('created',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_mfa_recovery_requests_user_id','mfa_recovery_requests',['user_id'])
    if op.get_bind().dialect.name=='postgresql':
        op.execute('ALTER TABLE mfa_recovery_codes ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE mfa_recovery_codes FORCE ROW LEVEL SECURITY')
        predicate="user_id = nullif(current_setting('app.user_id',true),'')"
        op.execute(f'CREATE POLICY tenant_owner ON mfa_recovery_codes USING ({predicate}) WITH CHECK ({predicate})')

def downgrade():
    raise RuntimeError('Preserve security audit history. Use a reviewed forward migration.')
