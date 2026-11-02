from contextlib import asynccontextmanager
from sqlalchemy import text
from app.core.config import settings
from app.database.session import engine
from app.security.authentication import cache

@asynccontextmanager
async def lifespan(app):
    if settings.startup_connectivity_check:
        try:
            with engine.connect() as connection:
                connection.execute(text('SELECT 1'))
                if settings.app_env == 'production':
                    role = connection.execute(text('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()
                    if role[0] or role[1]:
                        raise RuntimeError('Restricted runtime database role required')
            cache.ping()
        except Exception:
            raise RuntimeError('Required database or Redis connectivity check failed') from None
    yield
