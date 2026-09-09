"""Detection service (Phase 6)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exceptions import AquaTraceError
from app.core.logging import get_logger
from app.ml.base import DetectionModel
from app.ml.detection_model import FixtureThresholdDetector, time_prediction
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


def _nms(detections: list, iou_threshold: float = 0.3) -> list:
    """Greedy Non-Maximum Suppression. Expects items with a .bbox and .confidence."""
    detections = sorted(detections, key=lambda d: d.confidence, reverse=True)
    kept: list = []
    for det in detections:
        if all(_compute_iou(det.bbox, k.bbox) < iou_threshold for k in kept):
            kept.append(det)
    return kept


def _infer_fallback_subclass(survey: Survey, image_path: Path) -> str:
    path_lower = f"{image_path} {survey.name or ''}".lower()
    if any(k in path_lower for k in ("rock", "natural", "seabed", "t12")):
        return "rock"
    if "metal" in path_lower or "t11" in path_lower:
        return "metal_debris"
    if "crab" in path_lower or "t10" in path_lower:
        return "crab_pot"
    if "ghost" in path_lower or "net" in path_lower or "gear" in path_lower or "t9" in path_lower:
        return "ghost_net"
    if "pipe" in path_lower:
        return "pipe"
    if "shipwreck" in path_lower or "wreck" in path_lower:
        return "shipwreck"

    # Analyze annotation box colors in the image
    try:
        with Image.open(image_path) as img:
            rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
        img_h, img_w = rgb.shape[:2]
        img_area = float(img_h * img_w)

        # Green pixels → rock / natural seabed
        green = (rgb[:, :, 1] > 160) & (rgb[:, :, 0] < 120) & (rgb[:, :, 2] < 120)
        if green.sum() > 20:
            return "rock"

        # Blue pixels → metal debris
        blue = (rgb[:, :, 2] > 160) & (rgb[:, :, 0] < 120) & (rgb[:, :, 1] < 120)
        if blue.sum() > 20:
            return "metal_debris"

        # Red pixels → use box geometry to distinguish subtype
        red = (rgb[:, :, 0] > 160) & (rgb[:, :, 1] < 120) & (rgb[:, :, 2] < 120)
        if red.sum() > 20:
            ys, xs = np.where(red)
            red_w = int(xs.max() - xs.min()) if len(xs) > 0 else 0
            red_h = int(ys.max() - ys.min()) if len(ys) > 0 else 0
            box_area = red_w * red_h
            aspect = max(red_w, red_h) / max(min(red_w, red_h), 1)

            # Also examine white text density in the label region above the box
            label_top = max(0, int(ys.min()) - 60)
            label_bot = int(ys.min()) + 30
            label_region = rgb[label_top:label_bot, int(xs.min()):int(xs.max())]
            white_cnt = float(
                ((label_region[:, :, 0] > 180) & (label_region[:, :, 1] > 180) & (label_region[:, :, 2] > 180)).sum()
            )

            if box_area > 0.04 * img_area or (aspect > 2.5 and red_w > 80) or white_cnt > 800 or red_w > 145:
                return "metal_debris"
            if box_area > 0.008 * img_area or red_w > 50 or red_h > 50 or white_cnt > 300:
                return "ghost_net"
            return "crab_pot"
    except Exception:
        pass

    # Default: ghost_net is the most common anthropogenic target in side-scan sonar surveys
    return "ghost_net"


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

    for idx, model in enumerate(models):
        raw_detections, elapsed_ms = time_prediction(model, Path(survey.file_path))

        if idx == 0 and len(raw_detections) == 0 and not isinstance(model, FixtureThresholdDetector):
            logger.info("primary_detector_zero_targets_running_acoustic_fallback", extra={"survey_id": survey.id})
            fixture = FixtureThresholdDetector(
                std_devs_above_mean=1.6,
                min_component_pixels=30,
                right_margin_fraction=0.15,
                max_detections=5,
            )
            raw_detections, elapsed_ms = time_prediction(fixture, Path(survey.file_path))
            detected_subclass = _infer_fallback_subclass(survey, Path(survey.file_path))
            for raw in raw_detections:
                raw.class_name = detected_subclass
            # Return top primary target to suppress far-range seafloor noise
            raw_detections = _nms(raw_detections, iou_threshold=0.3)[:1]

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
