"""Engine / session management.

The engine is created from ``DATABASE_URL``. SQLite gets ``check_same_thread=False``
because the camera pipelines (Phase 1+) run in worker threads, but nothing else is
SQLite-specific, so moving to Postgres is an Alembic run (SPEC §18).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def ensure_sqlite_dir(url: str) -> None:
    """Create the parent directory of a SQLite file so the DB can be created.

    Public because Alembic's env.py builds its own engine and must call this too:
    on a fresh clone ``backend/data/`` does not exist yet and SQLite will not
    create a missing directory (it fails with "unable to open database file").
    """
    prefix = "sqlite:///"
    if url.startswith(prefix):
        raw = url[len(prefix) :]
        if raw and raw != ":memory:":
            Path(raw).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def init_engine(database_url: str) -> Engine:
    """(Re)create the engine and session factory for ``database_url``."""
    global _engine, _SessionLocal
    ensure_sqlite_dir(database_url)
    kwargs: dict[str, object] = {"future": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    _engine = create_engine(database_url, **kwargs)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("database engine not initialised; call init_engine() first")
    return _engine


def create_all() -> None:
    """Create tables directly (used by tests and first run; Alembic owns migrations)."""
    Base.metadata.create_all(bind=get_engine())


def get_session() -> Session:
    if _SessionLocal is None:
        raise RuntimeError("session factory not initialised; call init_engine() first")
    return _SessionLocal()


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def db_dependency() -> Iterator[Session]:
    """FastAPI dependency yielding a session."""
    session = get_session()
    try:
        yield session
    finally:
        session.close()
