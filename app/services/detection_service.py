"""Detection service (Phase 6)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exceptions import AquaTraceError
from app.core.logging import get_logger
from app.ml.base import DetectionModel
from app.ml.detection_model import time_prediction
from app.ml.model_registry import get_detection_model, get_shipwreck_detection_model
from app.models.detection import Detection
from app.models.survey import Survey

logger = get_logger(__name__)


class SurveyNotReadyForDetectionError(AquaTraceError):
    status_code = 409


def run_detection(db: Session, survey: Survey) -> list[Detection]:
    """Run every currently registered detection model against `survey`'s
    stored file and persist one `Detection` row per raw output.

    Two independent slots are run and merged, not one model chosen over
    the other -- see `app/ml/model_registry.py`'s module docstring.
    `get_detection_model()` (general-purpose: YOLO11s debris/gear, or
    `FixtureThresholdDetector` if untrained) always runs;
    `get_shipwreck_detection_model()` (E004, shipwreck-specialist) runs
    too whenever its checkpoint is registered. Each `Detection` row
    still records its own real `model_name`/`model_version`, so nothing
    about which model produced which row is lost by merging them into
    one survey's detection set.
    """
    if not survey.file_path:
        raise SurveyNotReadyForDetectionError(
            "Survey has no uploaded file to run detection against.", survey_id=survey.id
        )

    models: list[DetectionModel] = [get_detection_model()]
    shipwreck_model = get_shipwreck_detection_model()
    if shipwreck_model is not None:
        models.append(shipwreck_model)

    detections: list[Detection] = []
    for model in models:
        raw_detections, elapsed_ms = time_prediction(model, Path(survey.file_path))
        for raw in raw_detections:
            detection = Detection(
                survey_id=survey.id,
                bbox=raw.bbox,
                mask_path=raw.mask_path,
                class_name=raw.class_name,
                confidence=raw.confidence,
                requires_manual_review=raw.requires_manual_review,
                model_name=model.model_name,
                model_version=model.model_version,
                inference_time_ms=elapsed_ms / max(len(raw_detections), 1),
            )
            db.add(detection)
            detections.append(detection)

        logger.info(
            "detection_model_run_complete",
            extra={
                "survey_id": survey.id,
                "model_name": model.model_name,
                "detection_count": len(raw_detections),
                "elapsed_ms": elapsed_ms,
            },
        )

    db.commit()
    for detection in detections:
        db.refresh(detection)

    logger.info(
        "detection_run_complete",
        extra={
            "survey_id": survey.id,
            "models_run": [model.model_name for model in models],
            "detection_count": len(detections),
        },
    )
    return detections


def delete_detections_for_survey(db: Session, survey_id: str) -> int:
    """Deletes every Detection row for `survey_id` -- called by
    processing_service.run_pipeline() before a (re)run creates a fresh
    batch. Must be called after target_service.delete_targets_for_survey()
    (targets carry an optional detection_id, ON DELETE SET NULL -- not
    that ordering strictly matters here, since every target and every
    detection for this survey are being cleared together either way, but
    targets-then-detections mirrors the create order and avoids ever
    having a target point at nothing mid-transaction). See
    target_service.delete_targets_for_survey()'s docstring for the full
    replace-vs-accumulate reasoning."""
    result = db.execute(delete(Detection).where(Detection.survey_id == survey_id))
    db.commit()
    return result.rowcount


def list_detections(db: Session, survey_id: str) -> list[Detection]:
    return list(
        db.execute(
            select(Detection).where(Detection.survey_id == survey_id).order_by(Detection.confidence.desc())
        )
        .scalars()
        .all()
    )
