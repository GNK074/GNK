"""Read-only readiness checks. Runtime credentials never perform schema migrations."""
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from app.database.session import Base

class SchemaNotReady(RuntimeError):
    pass

MESSAGE = 'Database schema is not ready for this release. Back up the database, then run ./deploy/migrate_database.sh using the migration container before starting the backend.'

def check_schema(connection):
    config = Config(str(Path(__file__).resolve().parents[2] / 'alembic.ini'))
    expected = set(ScriptDirectory.from_config(config).get_heads())
    current = set(MigrationContext.configure(connection).get_current_heads())
    if current != expected:
        raise SchemaNotReady(MESSAGE)
    inspector = inspect(connection)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            raise SchemaNotReady(MESSAGE)
        actual = {column['name'] for column in inspector.get_columns(table.name)}
        if not set(table.c.keys()).issubset(actual):
            raise SchemaNotReady(MESSAGE)
