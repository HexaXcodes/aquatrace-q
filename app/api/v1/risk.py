"""Risk endpoint (Phase 20): GET /targets/{id}/risk"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AquaTraceError
from app.db.session import get_db
from app.models.risk import RiskScore
from app.schemas.risk import RiskScoreRead
from app.services import target_service

router = APIRouter(tags=["risk"])


class RiskNotAvailableError(AquaTraceError):
    status_code = 404


@router.get("/targets/{target_id}/risk", response_model=RiskScoreRead, summary="Get a target's risk score")
def get_target_risk(target_id: str, db: Session = Depends(get_db)) -> RiskScoreRead:
    target_service.get_target(db, target_id)
    risk = db.execute(select(RiskScore).where(RiskScore.target_id == target_id)).scalar_one_or_none()
    if risk is None:
        raise RiskNotAvailableError("No risk score yet -- run processing for this survey first.", target_id=target_id)
    return RiskScoreRead.model_validate(risk)
