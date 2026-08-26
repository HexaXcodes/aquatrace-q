"""Target endpoints (Phase 20): GET /surveys/{id}/targets, GET /targets/{id}"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.target import TargetList, TargetRead
from app.services import survey_service, target_service

router = APIRouter(tags=["targets"])


@router.get(
    "/surveys/{survey_id}/targets",
    response_model=TargetList,
    summary="List targets for a survey",
)
def list_targets(survey_id: str, db: Session = Depends(get_db)) -> TargetList:
    survey_service.get_survey(db, survey_id)
    items = target_service.list_targets(db, survey_id)
    return TargetList(items=[TargetRead.model_validate(t) for t in items], total=len(items))


@router.get("/targets/{target_id}", response_model=TargetRead, summary="Get a target")
def get_target(target_id: str, db: Session = Depends(get_db)) -> TargetRead:
    target = target_service.get_target(db, target_id)
    return TargetRead.model_validate(target)
