"""FastAPI DB session dependency, plus an overridable session factory for
code that runs outside a request (e.g. BackgroundTasks), which cannot
use FastAPI's `Depends`-based override mechanism."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from app.db.database import SessionLocal

_session_factory_override: sessionmaker | None = None


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def get_session_factory() -> sessionmaker:
    """Returns the sessionmaker to use for a fresh session. Defaults to
    the production `SessionLocal`; tests override it via
    `set_session_factory_override` so background tasks use the same
    in-memory database as the rest of the test."""
    return _session_factory_override or SessionLocal


def set_session_factory_override(factory: sessionmaker) -> None:
    global _session_factory_override
    _session_factory_override = factory


def clear_session_factory_override() -> None:
    global _session_factory_override
    _session_factory_override = None
