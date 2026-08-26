"""Detection service (Phase 6)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AquaTraceError
from app.core.logging import get_logger
from app.ml.detection_model import time_prediction
from app.ml.model_registry import get_detection_model
from app.models.detection import Detection
from app.models.survey import Survey

logger = get_logger(__name__)


class SurveyNotReadyForDetectionError(AquaTraceError):
    status_code = 409


def run_detection(db: Session, survey: Survey) -> list[Detection]:
    """Run the currently registered detection model against `survey`'s
    stored file and persist one `Detection` row per raw output."""
    if not survey.file_path:
        raise SurveyNotReadyForDetectionError(
            "Survey has no uploaded file to run detection against.", survey_id=survey.id
        )

    model = get_detection_model()
    raw_detections, elapsed_ms = time_prediction(model, Path(survey.file_path))

    detections: list[Detection] = []
    for raw in raw_detections:
        detection = Detection(
            survey_id=survey.id,
            bbox=raw.bbox,
            mask_path=raw.mask_path,
            class_name=raw.class_name,
            confidence=raw.confidence,
            model_name=model.model_name,
            model_version=model.model_version,
            inference_time_ms=elapsed_ms / max(len(raw_detections), 1),
        )
        db.add(detection)
        detections.append(detection)

    db.commit()
    for detection in detections:
        db.refresh(detection)

    logger.info(
        "detection_run_complete",
        extra={
            "survey_id": survey.id,
            "model_name": model.model_name,
            "detection_count": len(detections),
            "elapsed_ms": elapsed_ms,
        },
    )
    return detections


def list_detections(db: Session, survey_id: str) -> list[Detection]:
    return list(
        db.execute(
            select(Detection).where(Detection.survey_id == survey_id).order_by(Detection.confidence.desc())
        )
        .scalars()
        .all()
    )
