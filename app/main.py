"""
AquaTrace-Q backend entrypoint.

Run locally with:

    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

See README.md for the full setup, migration, and Docker instructions.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_directories()
    logger.info(
        "application_startup",
        extra={"app": settings.APP_NAME, "version": settings.APP_VERSION, "env": settings.ENV},
    )
    yield
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Quantum-Assisted Autonomous Marine Debris Triage & Verification "
            "System for Coral Reef Conservation -- backend API. "
            "Phases implemented: 1 (scaffolding), 2 (schema/models), "
            "3 (migrations), 4 (application), 5 (survey ingestion)."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/health", tags=["health"], summary="Liveness/readiness check")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}

    return app


app = create_app()
