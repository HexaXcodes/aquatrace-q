"""Environment endpoint (Phase 20): GET /targets/{id}/environment"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import AquaTraceError
from app.db.session import get_db
from app.schemas.environment import EnvironmentContextRead
from app.services import environment_service, target_service

router = APIRouter(tags=["environment"])


class EnvironmentNotAvailableError(AquaTraceError):
    status_code = 404


@router.get(
    "/targets/{target_id}/environment",
    response_model=EnvironmentContextRead,
    summary="Get a target's reef/MPA environmental context",
)
def get_target_environment(target_id: str, db: Session = Depends(get_db)) -> EnvironmentContextRead:
    target_service.get_target(db, target_id)  # 404s if target doesn't exist
    context = environment_service.get_environment_context(db, target_id)
    if context is None:
        raise EnvironmentNotAvailableError(
            "No environment context yet -- target has not been geolocated/enriched.",
            target_id=target_id,
        )
    return EnvironmentContextRead.model_validate(context)
