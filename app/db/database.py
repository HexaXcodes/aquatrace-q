"""
SQLAlchemy engine + declarative base.

One engine per process, created from `DATABASE_URL`. Production/dev use
PostgreSQL + PostGIS; tests override this engine with an in-memory
SQLite database (see `tests/conftest.py`) so the suite runs without a
live Postgres instance.
"""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models (used by Alembic autogenerate)."""


def enable_sqlite_foreign_keys(engine) -> None:
    """Turns on real FK constraint enforcement (including `ON DELETE
    CASCADE`) for a SQLite engine, which SQLite otherwise silently
    ignores per-connection unless told to enforce it -- unlike Postgres
    (the real prod/staging database), which enforces FKs by default.
    Without this, a bulk delete that relies on `ondelete=CASCADE`
    (e.g. target_service.delete_targets_for_survey()) would genuinely
    cascade in Postgres but silently leave orphaned child rows behind in
    SQLite -- a real dev/prod behavior gap, not a style nit.

    Called both here for the app's real engine (below) and in
    `tests/conftest.py` for the separate in-memory engine the test suite
    builds -- factored out rather than duplicated so the two can't drift
    out of sync with each other.
    """

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _make_engine():
    connect_args: dict[str, object] = {}
    is_sqlite = settings.DATABASE_URL.startswith("sqlite")
    if is_sqlite:
        # Needed for SQLite when the same connection is shared across threads,
        # which happens under the FastAPI TestClient.
        connect_args["check_same_thread"] = False

    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        pool_pre_ping=True,
        connect_args=connect_args,
    )

    if is_sqlite:
        enable_sqlite_foreign_keys(engine)

    return engine


engine = _make_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
