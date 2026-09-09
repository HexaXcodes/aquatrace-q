"""Image endpoint: GET /surveys/{id}/image

Streams a survey's real uploaded sonar image bytes back to the client.
Added specifically so the frontend's Triage Overlay "UPLOADED (RAW
ACOUSTIC SONAR)" panel can display the actual image instead of the
honest placeholder it used until now -- this route didn't exist when
that placeholder decision was made (see docs/ml-integration.md and the
frontend's own comment on that panel).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import survey_service

router = APIRouter(tags=["images"])


@router.get(
    "/surveys/{survey_id}/image",
    summary="Get the survey's real uploaded sonar image bytes",
)
def get_survey_image(survey_id: str, db: Session = Depends(get_db)) -> FileResponse:
    survey = survey_service.get_survey(db, survey_id)
    path, content_type = survey_service.get_survey_image_path(survey)
    return FileResponse(path=path, media_type=content_type)
