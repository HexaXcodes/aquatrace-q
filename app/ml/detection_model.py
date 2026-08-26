"""
`FixtureThresholdDetector` -- the detector used until Shaun/Shashank
register a real trained model.

This is NOT a placeholder that returns invented numbers: it genuinely
analyzes the uploaded sonar image (intensity thresholding + connected-
component labeling via `scipy.ndimage`) and returns real bounding boxes
around the brightest connected regions, which is a legitimate (if
crude) classical target-detection technique for side-scan sonar
waterfalls. What it explicitly is NOT is a trained classifier -- every
detection it produces is tagged with `model_name="fixture-threshold-detector"`
so nothing downstream can mistake it for the real model's output.

Registering the real model later is a two-step change:
  1. implement `DetectionModel.predict()` against the trained weights,
  2. register it in `app/ml/model_registry.py`.
Nothing else in the codebase changes.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from app.ml.base import DetectionModel, RawDetection


class FixtureThresholdDetector(DetectionModel):
    model_name = "fixture-threshold-detector"
    model_version = "test-fixture-1"

    def __init__(
        self,
        *,
        std_devs_above_mean: float = 1.5,
        min_component_pixels: int = 25,
        max_detections: int = 20,
    ) -> None:
        self.std_devs_above_mean = std_devs_above_mean
        self.min_component_pixels = min_component_pixels
        self.max_detections = max_detections

    def predict(self, image_path: Path) -> list[RawDetection]:
        with Image.open(image_path) as img:
            gray = np.asarray(img.convert("L"), dtype=np.float32)

        threshold = gray.mean() + self.std_devs_above_mean * gray.std()
        mask = gray > threshold

        labeled, num_components = ndimage.label(mask)
        if num_components == 0:
            return []

        component_sizes = ndimage.sum(mask, labeled, index=range(1, num_components + 1))
        slices = ndimage.find_objects(labeled)

        detections: list[RawDetection] = []
        for component_index, size in enumerate(component_sizes, start=1):
            if size < self.min_component_pixels:
                continue
            region = slices[component_index - 1]
            y_slice, x_slice = region
            bbox = [
                float(x_slice.start),
                float(y_slice.start),
                float(x_slice.stop),
                float(y_slice.stop),
            ]
            # Confidence is a simple, transparent function of how far above
            # background the component's peak intensity is -- not a
            # calibrated probability. It exists so downstream stages have
            # *something* ordinal to sort on before a real model is wired in.
            peak_intensity = float(gray[y_slice, x_slice].max())
            spread = max(float(gray.std()), 1e-6)
            raw_score = (peak_intensity - float(gray.mean())) / (spread * 4.0)
            confidence = float(np.clip(raw_score, 0.05, 0.95))

            detections.append(
                RawDetection(class_name="ANTHROPOGENIC", confidence=confidence, bbox=bbox)
            )

        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections[: self.max_detections]


def time_prediction(model: DetectionModel, image_path: Path) -> tuple[list[RawDetection], float]:
    """Run `model.predict` and return (detections, elapsed_ms). Shared by
    the detection service so timing is measured consistently regardless of
    which concrete model is registered."""
    start = time.perf_counter()
    detections = model.predict(image_path)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return detections, elapsed_ms
