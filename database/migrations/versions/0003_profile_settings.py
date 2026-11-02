"""Persist private profile details and appearance."""
from alembic import op
import sqlalchemy as sa
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

def upgrade():
    for column in [sa.Column('gender', sa.String(30)), sa.Column('date_of_birth', sa.Date()),
                   sa.Column('mobile', sa.String(20)),
                   sa.Column('theme', sa.String(20), nullable=False, server_default='carbon_black'),
                   sa.Column('avatar_data', sa.LargeBinary()),
                   sa.Column('avatar_version', sa.Integer(), nullable=False, server_default='0')]:
        op.add_column('users', column)
    op.add_column('tokens', sa.Column('target_email', sa.String(254)))

def downgrade():
    op.drop_column('tokens', 'target_email')
    for name in ['avatar_version', 'avatar_data', 'theme', 'mobile', 'date_of_birth', 'gender']:
        op.drop_column('users', name)
