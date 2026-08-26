"""
Aggregates every `/api/v1/*` resource router.
"""

from fastapi import APIRouter

from app.api.v1 import (
    classification,
    detections,
    environment,
    experiments,
    missions,
    priority,
    processing,
    reports,
    risk,
    surveys,
    targets,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(surveys.router)
api_router.include_router(processing.router)
api_router.include_router(detections.router)
api_router.include_router(targets.router)
api_router.include_router(classification.router)
api_router.include_router(environment.router)
api_router.include_router(risk.router)
api_router.include_router(priority.router)
api_router.include_router(missions.router)
api_router.include_router(reports.router)
api_router.include_router(experiments.router)
