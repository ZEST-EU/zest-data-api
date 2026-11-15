"""Database engine, session factory, declarative base, and portable column types.

The models target PostgreSQL in production (BIGINT identity), but use a dialect
variant for the surrogate PK so the full schema also works on SQLite — which lets
the test suite run against an in-memory database with no external services.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import BigInteger, Integer, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

# --- Portable column types --------------------------------------------------
# PostgreSQL gets a BIGINT identity; SQLite (tests) gets a plain INTEGER PK.
BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""


# --- Engine / session (lazy singletons) -------------------------------------
_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine():
    """Return the process-wide SQLAlchemy engine, building it on first use."""
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args = {}
        if settings.database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_engine(
            settings.database_url,
            echo=settings.db_echo,
            future=True,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        if settings.database_url.startswith("sqlite"):
            # SQLite ignores FK constraints unless told otherwise; match Postgres.
            @event.listens_for(_engine, "connect")
            def _enable_sqlite_fks(dbapi_conn, _record):  # pragma: no cover - trivial
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()

    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    """Return the session factory bound to the engine."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autoflush=False, expire_on_commit=False, future=True
        )
    return _SessionLocal


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a transactional session per request."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


def reset_engine() -> None:
    """Dispose and drop the cached engine/sessionmaker (used by tests)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
