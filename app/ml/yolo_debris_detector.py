"""
`YoloDebrisDetector` -- adapts the trained YOLO11s marine debris/gear
detector to the `DetectionModel` interface.

Unlike E004 (a segmenter wrapped to look like a detector), this model is
a native fit for `DetectionModel`: it already outputs bounding boxes,
per-box class IDs, and per-box confidences directly from
`ultralytics.YOLO.predict()`, no mask-to-bbox adapter needed.

Trained on the same public Marine Debris FLS Dataset (real ARIS Explorer
3000 forward-looking-sonar imagery) already used for this project's
classical/quantum classifier training data
(`scripts/build_fls_training_data.py`, `docs/ml-integration.md`'s
"Current training status" section) -- but a different task: object
detection across whole sonar frames (3-class: marine_debris/
gear_hardware/other_anthropogenic), not classification of pre-cropped
96x96 target images (6-class: background/tire/chain/propeller/can/
bottle). The two models' vocabularies don't overlap, which is exactly
why `classification_service._detector_protected_class()` (built for
E004) also protects this model's output for free -- see
`docs/ml-integration.md`.

Real measured metrics (YOLO_TrainedModel/results.csv, epoch 60 of 60,
cited here, not re-derived): precision 0.961, recall 0.982, mAP50 0.983,
mAP50-95 0.801.
"""

from __future__ import annotations

from pathlib import Path

from app.ml.base import DetectionModel, RawDetection

# From YOLO_TrainedModel/model_contract.json -- the model authors' own
# declared thresholds, not values invented here.
_DEFAULT_CONFIDENCE_THRESHOLD = 0.5
_MANUAL_REVIEW_RANGE = (0.25, 0.5)  # [low, high) confidence -> flagged


class UltralyticsUnavailableError(RuntimeError):
    """Raised when ultralytics is not importable in this environment."""


def _requires_manual_review(
    confidence: float, default_confidence_threshold: float, manual_review_range: tuple[float, float]
) -> bool:
    """Pure boundary check, factored out of `predict()` so it's testable
    without an ultralytics `Results` object: True iff `confidence` falls
    in `[manual_review_range[0], default_confidence_threshold)`."""
    return manual_review_range[0] <= confidence < default_confidence_threshold


class YoloDebrisDetector(DetectionModel):
    model_name = "yolo11s-marine-debris-fls"
    model_version = "v1"

    def __init__(
        self,
        checkpoint_path: Path,
        *,
        default_confidence_threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD,
        manual_review_range: tuple[float, float] = _MANUAL_REVIEW_RANGE,
    ) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:  # pragma: no cover - exercised only when ultralytics uninstalled
            raise UltralyticsUnavailableError(
                "ultralytics is not importable in this environment. Install it "
                "(`pip install ultralytics==8.4.129`) per requirements.txt."
            ) from exc

        self.default_confidence_threshold = default_confidence_threshold
        self.manual_review_range = manual_review_range
        self._model = YOLO(str(checkpoint_path))

    def predict(self, image_path: Path) -> list[RawDetection]:
        # conf=manual_review_range[0]: the model contract's own floor below
        # which a detection isn't reported at all, not just "not flagged."
        # Passed explicitly rather than relying on ultralytics' own default
        # (which happens to also be 0.25) -- that would be a coincidence
        # this code shouldn't depend on silently holding.
        results = self._model.predict(
            source=str(image_path), conf=self.manual_review_range[0], verbose=False
        )
        result = results[0]
        boxes = result.boxes

        detections: list[RawDetection] = []
        for i in range(len(boxes)):
            confidence = float(boxes.conf[i].item())
            class_id = int(boxes.cls[i].item())
            class_name = self._model.names[class_id]
            x1, y1, x2, y2 = boxes.xyxy[i].tolist()

            requires_manual_review = _requires_manual_review(
                confidence, self.default_confidence_threshold, self.manual_review_range
            )

            detections.append(
                RawDetection(
                    class_name=class_name,
                    confidence=confidence,
                    bbox=[float(x1), float(y1), float(x2), float(y2)],
                    requires_manual_review=requires_manual_review,
                )
            )
        return detections
