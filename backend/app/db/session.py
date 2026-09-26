from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _create_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)


@lru_cache(maxsize=8)
def get_engine(database_url: str | None = None) -> Engine:
    settings = get_settings()
    resolved_url = database_url or settings.database_url
    if resolved_url.startswith("sqlite:///"):
        database_path = Path(resolved_url.removeprefix("sqlite:///"))
        database_path.parent.mkdir(parents=True, exist_ok=True)
    return _create_engine(resolved_url)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    session_factory = create_session_factory(get_engine())
    with session_factory() as session:
        yield session
