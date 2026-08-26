"""Mission endpoints (Phase 20): POST /surveys/{id}/missions, GET /missions/{id}"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.mission import MissionCreate, MissionRead
from app.services import mission_service, survey_service

router = APIRouter(tags=["missions"])


@router.post(
    "/surveys/{survey_id}/missions",
    response_model=MissionRead,
    status_code=201,
    summary="Build a ranked verification mission for a survey's targets",
)
def create_mission(survey_id: str, payload: MissionCreate, db: Session = Depends(get_db)) -> MissionRead:
    survey_service.get_survey(db, survey_id)
    mission = mission_service.build_mission(
        db,
        survey_id,
        start_latitude=payload.start_latitude,
        start_longitude=payload.start_longitude,
        vehicle_speed_mps=payload.vehicle_speed_mps,
    )
    return MissionRead.model_validate(mission)


@router.get("/missions/{mission_id}", response_model=MissionRead, summary="Get a mission")
def get_mission(mission_id: str, db: Session = Depends(get_db)) -> MissionRead:
    mission = mission_service.get_mission(db, mission_id)
    return MissionRead.model_validate(mission)
