"""Dependency checks with actionable messages that never include secret values."""
from contextlib import asynccontextmanager
from sqlalchemy import text
from redis.exceptions import AuthenticationError
from app.core.config import settings
from app.database.session import engine
from app.security.authentication import cache

class StartupCheckError(RuntimeError):
    pass

def check_dependencies(database,redis_client,production=False):
    try:
        with database.connect() as connection:
            connection.execute(text('SELECT 1'))
            if production:
                role=connection.execute(text('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()
                if role[0] or role[1]:
                    raise StartupCheckError('Database runtime role is privileged. Use the restricted gnk_app role; do not disable RLS checks.')
    except StartupCheckError:
        raise
    except Exception as error:
        original=getattr(error,'orig',error)
        code=getattr(original,'sqlstate',None) or getattr(original,'pgcode',None)
        if code=='28P01':
            message='Database authentication failed. Check that the existing gnk_app role password matches its mounted secret; do not regenerate passwords.'
        elif code=='28000':
            message='Database authorization failed. Verify the gnk_app role exists and is allowed to log in.'
        elif code=='3D000':
            message='Configured database does not exist. Verify the database name and existing persistent database.'
        elif code=='42501':
            message='Database privileges are insufficient. Review runtime-role grants and migrations.'
        else:
            message='Database connectivity check failed. Verify PostgreSQL is healthy, its hostname/port and runtime credentials. No connection details are logged.'
        raise StartupCheckError(message) from None
    try:
        redis_client.ping()
    except AuthenticationError:
        raise StartupCheckError('Redis authentication failed. Verify the mounted Redis secret matches the running Redis configuration.') from None
    except Exception:
        raise StartupCheckError('Redis connectivity check failed. Verify Redis is healthy and REDIS_URL points to the internal service.') from None

@asynccontextmanager
async def lifespan(app):
    if settings.startup_connectivity_check:
        check_dependencies(engine,cache,production=settings.app_env=='production')
    yield
