"""
Shared pytest fixtures.

Tests run against an in-memory SQLite database, not the real
PostgreSQL/PostGIS instance -- this keeps the suite fast and dependency-free
in CI/sandboxes while still exercising the exact same models, schemas,
services, and API routes used in production. Anything genuinely
PostGIS-specific (spatial queries) is introduced with its own
Postgres-backed test setup starting in Phase 12.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.database import enable_sqlite_foreign_keys
from app.db.session import (
    clear_session_factory_override,
    get_db,
    set_session_factory_override,
)
from app.gis.registry import reset_gis_registry_cache
from app.main import app
from app.ml.model_registry import reset_registry_cache


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    """Tests must never be at the mercy of whatever's sitting in the
    developer's real .env or real MODEL_DIRECTORY. get_settings() is
    @lru_cache'd, and get_reef_provider()/get_mpa_provider()/
    get_classical_classifier()/get_quantum_classifier() are separate
    caches layered on top of it -- so unrelated manual testing (e.g.
    temporarily flipping GIS_ENABLED, or dropping a trained model into
    the default `models/` directory to check registration works) can
    silently leak into test results unless all of these are reset
    together.

    Disabling env_file isolates env-gated settings (GIS_ENABLED, risk
    thresholds, ...) back to their class defaults. That alone is *not*
    enough for the model registry, though: MODEL_DIRECTORY's class
    default is the real `models/` directory, and get_classical_classifier()
    / get_quantum_classifier() gate purely on whether a file exists there
    -- not on any settings flag -- so a model file left on disk for
    manual testing still leaks in even with env_file disabled. Redirect
    MODEL_DIRECTORY to a per-test tmp_path so the registry never sees the
    developer's real model directory.
    """
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("MODEL_DIRECTORY", str(tmp_path / "models"))
    get_settings.cache_clear()
    reset_gis_registry_cache()
    reset_registry_cache()
    yield
    get_settings.cache_clear()
    reset_gis_registry_cache()
    reset_registry_cache()


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # This is a separate engine from app/db/database.py's real one (an
    # in-memory SQLite one, built directly here), so it needs the same
    # PRAGMA foreign_keys=ON call independently -- otherwise a test that
    # exercises a real ON DELETE CASCADE (e.g. target_service.
    # delete_targets_for_survey()) would silently pass here while only
    # actually cascading against the real dev/prod engine.
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine) -> Generator[Session, None, None]:
    TestingSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_engine) -> Generator[TestClient, None, None]:
    TestingSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def _override_get_db() -> Generator[Session, None, None]:
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    set_session_factory_override(TestingSessionLocal)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    clear_session_factory_override()
