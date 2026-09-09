"""Detection service (Phase 6)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exceptions import AquaTraceError
from app.core.logging import get_logger
from app.ml.base import DetectionModel
from app.ml.detection_model import time_prediction
from app.ml.model_registry import get_detection_model, get_shipwreck_detection_model, reset_registry_cache
from app.models.detection import Detection
from app.models.survey import Survey

logger = get_logger(__name__)


class SurveyNotReadyForDetectionError(AquaTraceError):
    status_code = 409


def _compute_iou(box1: list[float], box2: list[float]) -> float:
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if intersection <= 0:
        return 0.0

    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection
    return intersection / union if union > 0 else 0.0


def run_detection(db: Session, survey: Survey) -> list[Detection]:
    """Run every currently registered detection model against `survey`'s
    stored file and persist one `Detection` row per raw output.
    """
    if not survey.file_path:
        raise SurveyNotReadyForDetectionError(
            "Survey has no uploaded file to run detection against.", survey_id=survey.id
        )

    # Clear cached model singletons so live registry changes are picked up immediately
    reset_registry_cache()

    models: list[DetectionModel] = [get_detection_model()]
    shipwreck_model = get_shipwreck_detection_model()
    if shipwreck_model is not None:
        models.append(shipwreck_model)

    all_raw: list[tuple[DetectionModel, RawDetection, float]] = []
    debris_boxes: list[list[float]] = []

    for model in models:
        raw_detections, elapsed_ms = time_prediction(model, Path(survey.file_path))
        per_item_ms = elapsed_ms / max(len(raw_detections), 1)

        for raw in raw_detections:
            # Track general debris/gear boxes for IoU suppression against false shipwreck detections
            if raw.class_name in ("marine_debris", "gear_hardware", "other_anthropogenic", "ghost_net"):
                debris_boxes.append(raw.bbox)
            all_raw.append((model, raw, per_item_ms))

        logger.info(
            "detection_model_run_complete",
            extra={
                "survey_id": survey.id,
                "model_name": model.model_name,
                "detection_count": len(raw_detections),
                "elapsed_ms": elapsed_ms,
            },
        )

    detections: list[Detection] = []
    for model, raw, inference_time in all_raw:
        # Suppress shipwreck false positive if it overlaps with a general marine debris/gear detection
        if raw.class_name == "shipwreck" and any(_compute_iou(raw.bbox, dbox) > 0.15 for dbox in debris_boxes):
            logger.info(
                "shipwreck_detection_suppressed_by_debris_overlap",
                extra={"survey_id": survey.id, "bbox": raw.bbox, "confidence": raw.confidence},
            )
            continue

        detection = Detection(
            survey_id=survey.id,
            bbox=raw.bbox,
            mask_path=raw.mask_path,
            class_name=raw.class_name,
            confidence=raw.confidence,
            requires_manual_review=raw.requires_manual_review,
            model_name=model.model_name,
            model_version=model.model_version,
            inference_time_ms=inference_time,
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
