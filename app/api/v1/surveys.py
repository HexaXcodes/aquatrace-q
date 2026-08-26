"""
Survey endpoints.

    POST /api/v1/surveys                     create a survey record
    POST /api/v1/surveys/{survey_id}/upload  attach + parse a sonar file
    GET  /api/v1/surveys/{survey_id}         fetch one survey
    GET  /api/v1/surveys                     list surveys

Later phases add `/surveys/{id}/process`, `/detections`, `/targets`,
etc. under this same router -- see `app/api/v1/router.py`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.survey import SurveyCreate, SurveyList, SurveyRead, SurveyUploadMetadata
from app.services import survey_service

router = APIRouter(prefix="/surveys", tags=["surveys"])


@router.post("", response_model=SurveyRead, status_code=201, summary="Create a survey")
def create_survey(payload: SurveyCreate, db: Session = Depends(get_db)) -> SurveyRead:
    """
    Create an empty survey record.

    A survey has no file, dimensions, or sonar metadata until a file is
    attached via `POST /surveys/{survey_id}/upload`. Splitting creation
    from upload lets the frontend show a survey as soon as the operator
    names it, before the (potentially large) file finishes uploading.
    """
    survey = survey_service.create_survey(db, payload)
    return SurveyRead.model_validate(survey)


@router.post(
    "/{survey_id}/upload",
    response_model=SurveyRead,
    summary="Upload a sonar file for an existing survey",
)
def upload_survey(
    survey_id: str,
    file: UploadFile = File(..., description="PNG, JPG/JPEG, or TIFF sonar image"),
    coordinate_reference_system: str | None = Form(default=None),
    origin_latitude: float | None = Form(default=None),
    origin_longitude: float | None = Form(default=None),
    meters_per_pixel: float | None = Form(default=None),
    depth_min: float | None = Form(default=None),
    depth_max: float | None = Form(default=None),
    sonar_frequency: float | None = Form(default=None),
    sensor_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> SurveyRead:
    """
    Attach a sonar file to a survey.

    The file is validated, streamed to disk under `UPLOAD_DIRECTORY`,
    and parsed with the `SonarParser` registered for its extension (see
    `app/parsers/`). Any acquisition metadata (CRS, meters-per-pixel,
    depth range, sonar frequency, sensor name) supplied as form fields is
    stored alongside it -- none of it is inferred from the image itself.

    Metadata fields are declared individually (rather than as a single
    `Form(SurveyUploadMetadata)` model) because combining a Pydantic
    form-model with a `File(...)` parameter on the same endpoint is
    unsupported in this FastAPI version -- it raises a spurious
    "field required" error for the whole model. Pydantic validation
    still happens via `SurveyUploadMetadata(**locals())` below.

    On success the survey's `status` moves from `CREATED` to `UPLOADED`.
    """
    metadata = SurveyUploadMetadata(
        coordinate_reference_system=coordinate_reference_system,
        origin_latitude=origin_latitude,
        origin_longitude=origin_longitude,
        meters_per_pixel=meters_per_pixel,
        depth_min=depth_min,
        depth_max=depth_max,
        sonar_frequency=sonar_frequency,
        sensor_name=sensor_name,
    )
    survey = survey_service.get_survey(db, survey_id)
    updated = survey_service.upload_survey_file(db, survey, file, metadata)
    return SurveyRead.model_validate(updated)


@router.get("/{survey_id}", response_model=SurveyRead, summary="Get a survey")
def get_survey(survey_id: str, db: Session = Depends(get_db)) -> SurveyRead:
    survey = survey_service.get_survey(db, survey_id)
    return SurveyRead.model_validate(survey)


@router.get("", response_model=SurveyList, summary="List surveys")
def list_surveys(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> SurveyList:
    items, total = survey_service.list_surveys(db, limit=limit, offset=offset)
    return SurveyList(
        items=[SurveyRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )
