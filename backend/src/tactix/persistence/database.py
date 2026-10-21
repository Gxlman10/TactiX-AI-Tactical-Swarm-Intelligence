"""Database connections; callers own transaction boundaries."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from tactix.config import Settings


def build_engine(url: str | None = None) -> Engine:
    return create_engine(url or Settings().database_url, pool_pre_ping=True)


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
