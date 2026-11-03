from app.market_data import models as market_models
from app.compliance import models as compliance_models
from alembic import context
from app.database.session import Base, engine
from app.models import identity, trading
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
