from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from threading import RLock

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _create_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _set_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


def get_engine(database_url: str | None = None) -> Engine:
    settings = get_settings()
    resolved_url = database_url or settings.database_url
    return _cached_engine(resolved_url)


@lru_cache(maxsize=8)
def _cached_engine(resolved_url: str) -> Engine:
    if resolved_url.startswith("sqlite:///"):
        database_path = Path(resolved_url.removeprefix("sqlite:///"))
        database_path.parent.mkdir(parents=True, exist_ok=True)
    return _create_engine(resolved_url)


_runtime_guard = RLock()
_runtime_engine: Engine | None = None
_runtime_sessions: set[Session] = set()


@contextmanager
def database_lifetime(database_url: str):
    """Entered only under the ASGI usage lease; shut down before lease release.

    Uvicorn drains requests before lifespan shutdown. Explicit tracking also
    closes any remaining application sessions before disposing pooled handles.
    """
    global _runtime_engine
    with _runtime_guard:
        if _runtime_engine is not None:
            raise RuntimeError("Database runtime already active")
        engine = get_engine(database_url)
        _runtime_engine = engine
    try:
        yield engine
    finally:
        with _runtime_guard:
            _runtime_engine = None  # Refuse new sessions during shutdown.
            failures = []
            try:
                for session in tuple(_runtime_sessions):
                    try:
                        session.close()
                    except Exception as exc:
                        failures.append(exc)
                    else:
                        _runtime_sessions.discard(session)
            finally:
                engine.dispose()
            if failures:
                raise ExceptionGroup("Database session shutdown failed", failures)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with _runtime_guard:
        if _runtime_engine is None:
            raise RuntimeError("Database runtime is not active")
        session = create_session_factory(_runtime_engine)()
        _runtime_sessions.add(session)
    try:
        yield session
    finally:
        with _runtime_guard:
            session.close()
            _runtime_sessions.discard(session)
