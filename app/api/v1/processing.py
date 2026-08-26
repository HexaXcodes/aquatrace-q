"""
Processing endpoints (Phases 18-20): POST /surveys/{id}/process, GET /jobs/{id}

Async processing note (Phase 19): this uses FastAPI's `BackgroundTasks`
rather than Celery+Redis. Justification: the pipeline for one survey
(a handful of targets, classical + quantum classification on small
feature vectors) runs in low single-digit seconds, not minutes -- the
complexity of a broker, worker pool, and separate deployable process
buys nothing at this scale and this stage of the project, and could not
be exercised in this sandbox anyway (no Redis available to test
against). What genuinely matters -- the API not blocking the caller,
and job status being pollable -- is provided by `BackgroundTasks` +
`ProcessingJob` here. If per-survey processing time grows materially
(e.g. once real CNN/QML inference replaces the fixtures), swapping the
background task body for a Celery task is a contained change: the
`ProcessingJob` row, `run_pipeline()`, and every other API route are
unaffected.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import JobNotFoundError
from app.db.session import get_db, get_session_factory
from app.models.processing_job import ProcessingJob
from app.schemas.processing import ProcessingJobRead, ProcessingRequest
from app.services import processing_service, survey_service

router = APIRouter(tags=["processing"])


def _run_pipeline_in_background(job_id: str, survey_id: str, mission_start: tuple[float, float] | None) -> None:
    """Runs in a fresh DB session -- the request-scoped session from
    `Depends(get_db)` may already be closed by the time a background
    task executes. Uses `get_session_factory()` (rather than importing
    `SessionLocal` directly) so tests, which override the factory, see
    the same in-memory database the rest of the test uses."""
    from app.models.survey import Survey as SurveyModel

    db = get_session_factory()()
    try:
        job = db.get(ProcessingJob, job_id)
        survey = db.get(SurveyModel, survey_id)
        if job is None or survey is None:
            return
        processing_service.run_pipeline(db, job, survey, mission_start=mission_start)
    finally:
        db.close()


@router.post(
    "/surveys/{survey_id}/process",
    response_model=ProcessingJobRead,
    status_code=202,
    summary="Kick off the full processing pipeline for a survey",
)
def start_processing(
    survey_id: str,
    payload: ProcessingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ProcessingJobRead:
    survey_service.get_survey(db, survey_id)  # 404s if the survey doesn't exist
    job = processing_service.create_job(db, survey_id)

    mission_start = None
    if payload.start_latitude is not None and payload.start_longitude is not None:
        mission_start = (payload.start_latitude, payload.start_longitude)

    background_tasks.add_task(_run_pipeline_in_background, job.id, survey_id, mission_start)
    return ProcessingJobRead.model_validate(job)


@router.get("/jobs/{job_id}", response_model=ProcessingJobRead, summary="Get processing job status")
def get_job(job_id: str, db: Session = Depends(get_db)) -> ProcessingJobRead:
    job = db.get(ProcessingJob, job_id)
    if job is None:
        raise JobNotFoundError(f"Processing job '{job_id}' does not exist.", job_id=job_id)
    return ProcessingJobRead.model_validate(job)
