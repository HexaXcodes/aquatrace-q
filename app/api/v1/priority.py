"""Priority endpoint (Phase 20): GET /targets/{id}/priority"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AquaTraceError
from app.db.session import get_db
from app.models.priority import PriorityScore
from app.schemas.priority import PriorityScoreRead
from app.services import target_service

router = APIRouter(tags=["priority"])


class PriorityNotAvailableError(AquaTraceError):
    status_code = 404


@router.get(
    "/targets/{target_id}/priority",
    response_model=PriorityScoreRead,
    summary="Get a target's verification priority",
)
def get_target_priority(target_id: str, db: Session = Depends(get_db)) -> PriorityScoreRead:
    target_service.get_target(db, target_id)
    priority = db.execute(
        select(PriorityScore).where(PriorityScore.target_id == target_id)
    ).scalar_one_or_none()
    if priority is None:
        raise PriorityNotAvailableError(
            "No priority score yet -- run processing for this survey first.", target_id=target_id
        )
    return PriorityScoreRead.model_validate(priority)
