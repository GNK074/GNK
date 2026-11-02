from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import settings, read_secret
url = make_url(settings.database_url.get_secret_value())
if settings.database_password_file:
    url = url.set(password=read_secret(settings.database_password_file))
options = {'pool_pre_ping': True}
if url.get_backend_name() != 'sqlite':
    options.update(pool_size=settings.db_pool_size, max_overflow=settings.db_max_overflow, pool_timeout=settings.db_pool_timeout, pool_recycle=settings.db_pool_recycle)
engine = create_engine(url, **options)
DB = sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def db():
    with DB() as session:
        yield session
