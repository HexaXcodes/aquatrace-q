"""
`DetectionModel` / `SegmentationModel` interfaces (Phase 6).

This is the entire integration boundary for Shaun and Shashank. The
backend calls `model.predict(image_path)` and gets back a list of
`RawDetection` -- it never imports torch, ultralytics, or any other
ML-framework-specific package directly. Swapping the registered model
from a fixture to a real trained YOLO/U-Net/DeepLab/Faster-R-CNN model
never touches `app/services/detection_service.py` or any API route.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RawDetection:
    """One model output. `bbox` and/or `mask_path` may be present depending
    on whether the model does detection, segmentation, or both.

    `requires_manual_review` is `None` unless the producing model declares
    its own confidence-band policy for "too uncertain to trust, but not
    low enough to discard" (e.g. the YOLO11s debris/gear detector's
    model_contract.json: 0.25-0.5 confidence -> manual review). `None`
    means "this model has no such policy," not "reviewed and cleared" --
    do not treat it as `False`. This is a raw-detection-confidence signal,
    deliberately separate from `uncertainty_service`'s classifier-
    probability entropy calculation; the two answer different questions
    and are never merged. See docs/ml-integration.md."""

    class_name: str
    confidence: float
    bbox: list[float] | None = None  # [x1, y1, x2, y2] in pixel space
    mask_path: str | None = None
    requires_manual_review: bool | None = None


class DetectionModel(abc.ABC):
    """Interface a bounding-box detector (e.g. YOLO, Faster R-CNN) implements."""

    #: Set by the concrete implementation; recorded on every `Detection` row.
    model_name: str = "unregistered"
    model_version: str = "0.0.0"

    @abc.abstractmethod
    def predict(self, image_path: Path) -> list[RawDetection]:
        """Run inference on a single sonar image and return raw detections."""
        raise NotImplementedError


class SegmentationModel(abc.ABC):
    """Interface a segmentation model (e.g. U-Net, DeepLab) implements."""

    model_name: str = "unregistered"
    model_version: str = "0.0.0"

    @abc.abstractmethod
    def predict(self, image_path: Path) -> list[RawDetection]:
        """Run inference on a single sonar image and return raw detections,
        each with a populated `mask_path` (written under OUTPUT_DIRECTORY)."""
        raise NotImplementedError
