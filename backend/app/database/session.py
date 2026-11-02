import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
engine = create_engine(os.getenv('DATABASE_URL', 'sqlite:///./gnk.db'), pool_pre_ping=True)
DB = sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def db():
    with DB() as session:
        yield session
