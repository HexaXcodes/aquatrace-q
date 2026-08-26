"""Detection endpoints (Phase 20): GET /surveys/{id}/detections"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.detection import DetectionList, DetectionRead
from app.services import detection_service, survey_service

router = APIRouter(tags=["detections"])


@router.get(
    "/surveys/{survey_id}/detections",
    response_model=DetectionList,
    summary="List raw detections for a survey",
)
def list_detections(survey_id: str, db: Session = Depends(get_db)) -> DetectionList:
    survey_service.get_survey(db, survey_id)  # 404s if the survey doesn't exist
    items = detection_service.list_detections(db, survey_id)
    return DetectionList(items=[DetectionRead.model_validate(d) for d in items], total=len(items))
