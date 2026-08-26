"""
End-to-end processing orchestration (Phase 18).

Runs every stage of the pipeline against a single survey, updating a
`ProcessingJob` row's `status` and appending to its `stage_log` as it
goes, so the entire run is reconstructable afterward.

Failure handling follows spec section 18 exactly:
  - A missing/unusable survey file is a genuine failure -> job FAILED.
  - An optional component being unavailable (QML not trained, GIS not
    configured, a target with no geolocation metadata) is NOT a
    failure: it's recorded as an honest per-stage/per-target note, and
    the pipeline continues so the rest of the survey still gets fully
    processed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.enums import ModelRunStatus, ProcessingJobStatus
from app.models.priority import PriorityScore
from app.models.processing_job import ProcessingJob
from app.models.risk import RiskScore
from app.models.survey import Survey
from app.services import (
    classification_service,
    coordinate_service,
    detection_service,
    environment_service,
    feature_service,
    mission_service,
    priority_service,
    report_service,
    risk_service,
    target_service,
)

logger = get_logger(__name__)


def _log(job: ProcessingJob, stage: ProcessingJobStatus, status: str, message: str) -> None:
    job.status = stage
    job.stage_log = [
        *job.stage_log,
        {
            "stage": stage.value,
            "status": status,
            "message": message,
            "at": datetime.now(timezone.utc).isoformat(),
        },
    ]
    logger.info("processing_stage", extra={"job_id": job.id, "stage": stage.value, "status": status})


def create_job(db: Session, survey_id: str) -> ProcessingJob:
    job = ProcessingJob(survey_id=survey_id, status=ProcessingJobStatus.QUEUED, stage_log=[])
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


class _PipelineFailure(Exception):
    """Raised for genuine, unrecoverable pipeline failures (see module docstring)."""


def run_pipeline(
    db: Session,
    job: ProcessingJob,
    survey: Survey,
    mission_start: tuple[float, float] | None = None,
) -> ProcessingJob:
    try:
        _log(job, ProcessingJobStatus.VALIDATING, "OK", "Survey has an uploaded file; proceeding.")
        if not survey.file_path:
            raise _PipelineFailure("Survey has no uploaded file; cannot process.")
        db.add(job)
        db.commit()

        _log(
            job,
            ProcessingJobStatus.PREPROCESSING,
            "OK",
            "No preprocessing pipeline configured yet; using raw uploaded image as-is.",
        )
        db.add(job)
        db.commit()

        detections = detection_service.run_detection(db, survey)
        model_name = detections[0].model_name if detections else "n/a"
        _log(job, ProcessingJobStatus.DETECTING, "OK", f"{len(detections)} raw detection(s) from '{model_name}'.")
        db.add(job)
        db.commit()

        targets = target_service.create_targets_from_detections(db, detections)
        _log(job, ProcessingJobStatus.DETECTING, "OK", f"{len(targets)} target(s) created from detections.")
        db.add(job)
        db.commit()

        _run_classification_stage(db, job, survey, targets)
        _run_geolocation_stage(db, job, survey, targets)
        _run_gis_stage(db, job, targets)
        _run_risk_and_priority_stages(db, job, targets)
        _run_mission_stage(db, job, survey.id, mission_start)
        _run_reporting_stage(db, job, survey)

        _log(job, ProcessingJobStatus.COMPLETED, "OK", "Pipeline completed.")
        job.error_message = None
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    except _PipelineFailure as exc:
        return _fail_job(db, job, str(exc))
    except Exception as exc:  # noqa: BLE001 - orchestrator boundary: convert to a recorded failure
        logger.exception("processing_pipeline_unhandled_error", extra={"job_id": job.id})
        return _fail_job(db, job, f"Unhandled error: {exc}")


def _fail_job(db: Session, job: ProcessingJob, message: str) -> ProcessingJob:
    job.status = ProcessingJobStatus.FAILED
    job.error_message = message
    job.stage_log = [
        *job.stage_log,
        {
            "stage": ProcessingJobStatus.FAILED.value,
            "status": "FAILED",
            "message": message,
            "at": datetime.now(timezone.utc).isoformat(),
        },
    ]
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _run_classification_stage(db: Session, job: ProcessingJob, survey: Survey, targets) -> None:
    ok_count, not_trained_count = 0, 0
    qml_statuses: set[str] = set()

    for target in targets:
        feature_vector = feature_service.extract_and_store_features(db, target, survey)
        classical_record, quantum_record = classification_service.classify_target(db, target, feature_vector)
        if classical_record.run_status is ModelRunStatus.OK:
            ok_count += 1
        elif classical_record.run_status is ModelRunStatus.NOT_TRAINED:
            not_trained_count += 1
        qml_statuses.add(quantum_record.run_status.value)

    _log(
        job,
        ProcessingJobStatus.CLASSIFYING,
        "OK",
        f"Classical classification: {ok_count} OK, {not_trained_count} NOT_TRAINED "
        f"across {len(targets)} target(s).",
    )
    db.add(job)
    db.commit()

    _log(
        job,
        ProcessingJobStatus.QML_CLASSIFYING,
        "OK",
        f"Quantum classification statuses observed: {sorted(qml_statuses) or ['n/a']}.",
    )
    db.add(job)
    db.commit()


def _run_geolocation_stage(db: Session, job: ProcessingJob, survey: Survey, targets) -> None:
    geolocated = 0
    for target in targets:
        result = coordinate_service.geolocate_target(survey, target)
        if result.latitude is not None and result.longitude is not None:
            target.latitude = result.latitude
            target.longitude = result.longitude
            target.coordinate_source = result.source
            db.add(target)
            geolocated += 1

    db.commit()
    _log(
        job,
        ProcessingJobStatus.GEOLOCATING,
        "OK",
        f"{geolocated}/{len(targets)} target(s) geolocated (survey origin/meters_per_pixel required).",
    )
    db.add(job)
    db.commit()


def _run_gis_stage(db: Session, job: ProcessingJob, targets) -> None:
    enriched = 0
    for target in targets:
        context = environment_service.enrich_target_environment(db, target)
        if context is not None:
            enriched += 1

    _log(job, ProcessingJobStatus.GIS_ENRICHMENT, "OK", f"{enriched}/{len(targets)} target(s) GIS-enriched.")
    db.add(job)
    db.commit()


def _get_by_target(db: Session, model, target_id: str):
    return db.execute(select(model).where(model.target_id == target_id)).scalar_one_or_none()


def _run_risk_and_priority_stages(db: Session, job: ProcessingJob, targets) -> None:
    for target in targets:
        environment = environment_service.get_environment_context(db, target.id)
        risk_result = risk_service.compute_risk(target, environment)

        risk_row = _get_by_target(db, RiskScore, target.id) or RiskScore(target_id=target.id)
        risk_row.score = risk_result.score
        risk_row.level = risk_result.level
        risk_row.factors = [
            {"name": f.name, "contribution": f.contribution, "detail": f.detail} for f in risk_result.factors
        ]
        risk_row.weights_version = risk_result.weights_version
        db.add(risk_row)
        db.commit()
        db.refresh(risk_row)

        priority_result = priority_service.compute_priority(target, risk_result)
        priority_row = _get_by_target(db, PriorityScore, target.id) or PriorityScore(target_id=target.id)
        priority_row.score = priority_result.score
        priority_row.action = priority_result.action
        priority_row.recommended_method = priority_result.recommended_method
        priority_row.verification_required = priority_result.verification_required
        priority_row.reasons = priority_result.reasons
        db.add(priority_row)
        db.commit()

    _log(job, ProcessingJobStatus.RISK_SCORING, "OK", f"Risk computed for {len(targets)} target(s).")
    db.add(job)
    db.commit()
    _log(job, ProcessingJobStatus.PRIORITIZING, "OK", f"Priority computed for {len(targets)} target(s).")
    db.add(job)
    db.commit()


def _run_mission_stage(
    db: Session, job: ProcessingJob, survey_id: str, mission_start: tuple[float, float] | None
) -> None:
    if mission_start is None:
        _log(
            job,
            ProcessingJobStatus.MISSION_PLANNING,
            "SKIPPED",
            "No vehicle start coordinate supplied; mission planning skipped.",
        )
        db.add(job)
        db.commit()
        return

    start_lat, start_lon = mission_start
    mission = mission_service.build_mission(db, survey_id, start_lat, start_lon)
    _log(
        job,
        ProcessingJobStatus.MISSION_PLANNING,
        "OK",
        f"Mission {mission.id} built with {len(mission.targets)} stop(s).",
    )
    db.add(job)
    db.commit()


def _run_reporting_stage(db: Session, job: ProcessingJob, survey: Survey) -> None:
    report = report_service.generate_survey_report(db, survey)
    _log(job, ProcessingJobStatus.REPORTING, "OK", f"Report generated with {report.target_count} row(s).")
    db.add(job)
    db.commit()
