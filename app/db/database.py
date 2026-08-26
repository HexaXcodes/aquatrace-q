"""
SQLAlchemy engine + declarative base.

One engine per process, created from `DATABASE_URL`. Production/dev use
PostgreSQL + PostGIS; tests override this engine with an in-memory
SQLite database (see `tests/conftest.py`) so the suite runs without a
live Postgres instance.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models (used by Alembic autogenerate)."""


def _make_engine():
    connect_args: dict[str, object] = {}
    if settings.DATABASE_URL.startswith("sqlite"):
        # Needed for SQLite when the same connection is shared across threads,
        # which happens under the FastAPI TestClient.
        connect_args["check_same_thread"] = False

    return create_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


engine = _make_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
