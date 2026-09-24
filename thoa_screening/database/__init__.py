"""
Database engine, session factory, and declarative base for the THOA
screening system.

Uses SQLAlchemy 2.0 style throughout.  The database URL must be
provided via the ``THOA_DATABASE_URL`` environment variable or
explicitly passed to the factory functions.

IMPORTANT: Never store database credentials in source code.
"""

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    MappedAsDataclass,
    Session,
    sessionmaker,
)


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """
    SQLAlchemy 2.0 declarative base for all ORM models.

    Every model in this package inherits from ``Base``.  The metadata
    object on this class drives Alembic migrations and ``create_all()``.
    """
    pass


# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------

def get_engine(database_url: str | None = None, *, echo: bool = False) -> Engine:
    """
    Create a SQLAlchemy engine.

    Args:
        database_url: PostgreSQL connection string.  Falls back to the
            ``THOA_DATABASE_URL`` environment variable if not provided.
        echo: If ``True``, emit SQL statements to stdout (dev only).

    Returns:
        A configured ``Engine`` instance.

    Raises:
        ValueError: If no database URL is available.
    """
    url = database_url or os.environ.get("THOA_DATABASE_URL")
    if not url:
        raise ValueError(
            "Database URL not provided.  Set the THOA_DATABASE_URL "
            "environment variable or pass `database_url` explicitly."
        )
    kwargs = {"echo": echo, "pool_pre_ping": True}
    if not url.startswith("sqlite"):
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
    else:
        kwargs["connect_args"] = {"check_same_thread": False}

    return create_engine(url, **kwargs)


def get_session_factory(
    engine: Engine | None = None,
) -> sessionmaker[Session]:
    """
    Create a session factory bound to the given engine.

    If no engine is provided, one is created from the environment.
    """
    if engine is None:
        engine = get_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_session(
    engine: Engine | None = None,
) -> Generator[Session, None, None]:
    """
    Context-manager / generator that yields a session and handles
    commit/rollback/close automatically.

    Usage::

        for session in get_session(engine):
            session.add(...)
    """
    factory = get_session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
