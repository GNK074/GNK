"""GNK paper order lifecycle and position controls."""
from alembic import op
import sqlalchemy as sa

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('risk_configurations', sa.Column('paper_collateral', sa.Numeric(20, 4), nullable=False, server_default='100000'))
    op.add_column('orders', sa.Column('executed_at', sa.DateTime(timezone=True)))
    op.add_column('orders', sa.Column('execution_price', sa.Numeric(20, 4)))
    op.add_column('orders', sa.Column('execution_reason', sa.String(20)))
    op.add_column('orders', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('positions', sa.Column('product', sa.String(10), nullable=False, server_default='DELIVERY'))
    op.add_column('positions', sa.Column('stop_loss', sa.Numeric(20, 4)))
    op.add_column('positions', sa.Column('target', sa.Numeric(20, 4)))
    op.create_table(
        'paper_marks',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('symbol', sa.String(40), primary_key=True),
        sa.Column('price', sa.Numeric(20, 4), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
    )
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE paper_marks ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE paper_marks FORCE ROW LEVEL SECURITY')
        op.execute("""CREATE POLICY paper_mark_owner ON paper_marks
            USING (user_id = current_setting('app.user_id', true))
            WITH CHECK (user_id = current_setting('app.user_id', true))""")


def downgrade():
    op.drop_table('paper_marks')
    for column in ('target', 'stop_loss', 'product'):
        op.drop_column('positions', column)
    for column in ('version', 'execution_reason', 'execution_price', 'executed_at'):
        op.drop_column('orders', column)
    op.drop_column('risk_configurations', 'paper_collateral')
