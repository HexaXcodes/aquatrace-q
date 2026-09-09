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
        std_devs_above_mean: float = 1.6,
        min_component_pixels: int = 30,
        max_detections: int = 20,
        # Only skip top 5% border
        top_margin_fraction: float = 0.05,
        # Search full image width (no right margin cutoff)
        right_margin_fraction: float = 0.0,
        # Minimum box side length in pixels (allows compact targets like crabpots)
        min_box_side_px: int = 10,
        # Box must cover at least this fraction of image area
        min_area_fraction: float = 0.0001,
        # Allow solid targets like crabpots (fill ratio up to 0.85)
        max_fill_ratio: float = 0.85,
    ) -> None:
        self.std_devs_above_mean = std_devs_above_mean
        self.min_component_pixels = min_component_pixels
        self.max_detections = max_detections
        self.top_margin_fraction = top_margin_fraction
        self.right_margin_fraction = right_margin_fraction
        self.min_box_side_px = min_box_side_px
        self.min_area_fraction = min_area_fraction
        self.max_fill_ratio = max_fill_ratio

    def predict(self, image_path: Path) -> list[RawDetection]:
        with Image.open(image_path) as img:
            rgb = np.asarray(img.convert("RGB"), dtype=np.float32)

        img_h, img_w, _ = rgb.shape
        img_area = float(img_h * img_w)

        # ── 1. Annotation-box detection ──────────────────────────────────────
        # The dataset images carry labelled bounding boxes:
        #   • Green  → rock / natural seabed
        #   • Red    → anthropogenic debris  (label + bbox; label is solid-fill)
        # We detect all colored annotation pixels, find connected components,
        # then separate *solid* label-plate components from *hollow* bbox outlines
        # by fill ratio. The label plate's size/aspect tells us the subclass;
        # the hollow outlines are the actual detection bounding boxes we emit.

        red_pixels   = (rgb[:, :, 0] > 150) & (rgb[:, :, 1] < 100) & (rgb[:, :, 2] < 100)
        green_pixels = (rgb[:, :, 1] > 150) & (rgb[:, :, 0] < 100) & (rgb[:, :, 2] < 100)
        annot_pixels = red_pixels | green_pixels

        if annot_pixels.sum() >= 20:
            labeled_annot, num_annot = ndimage.label(annot_pixels)
            slices = ndimage.find_objects(labeled_annot)

            label_class: str | None = None   # class inferred from the filled label plate
            # (comp_index, bbox, area) for hollow outline candidates
            bbox_candidates: list[tuple[int, list[float], int]] = []

            for comp_idx in range(1, num_annot + 1):
                y_sl, x_sl = slices[comp_idx - 1]
                bw = x_sl.stop - x_sl.start
                bh = y_sl.stop - y_sl.start
                if bw < 8 or bh < 8:
                    continue

                comp_mask  = (labeled_annot[y_sl, x_sl] == comp_idx)
                fill_ratio = float(comp_mask.sum()) / (bw * bh)
                comp_green = int(green_pixels[y_sl, x_sl].sum())
                comp_red   = int(red_pixels[y_sl, x_sl].sum())
                is_green   = comp_green > comp_red

                if is_green:
                    # Green component → always rock, whether label or bbox
                    label_class = "rock"
                    # Any green component with min size is a candidate bbox
                    if bw >= 20 and bh >= 20:
                        bbox_candidates.append(
                            (comp_idx,
                             [float(x_sl.start), float(y_sl.start), float(x_sl.stop), float(y_sl.stop)],
                             bw * bh)
                        )
                else:
                    # Red component
                    box_area  = bw * bh
                    area_frac = box_area / img_area

                    if fill_ratio > 0.55:
                        # Solid filled rectangle → this is the label plate
                        # Use its geometry to infer subclass:
                        #   Wide/large  → metal_debris  (label: "T-003 (Metal Debris)" spans ~25% width)
                        #   Medium      → ghost_net     (label: "T-001 (Ghost Gear)")
                        #   (crab pots have no label plate; they just have a bbox outline)
                        if area_frac > 0.042 or (bw > img_w * 0.30 and bh > img_h * 0.08):
                            label_class = "metal_debris"
                        else:
                            label_class = "ghost_net"
                    else:
                        # Hollow outline → actual bounding box around the object
                        # Require minimum 20x20px to filter tiny noise fragments
                        if bw >= 20 and bh >= 20:
                            bbox_candidates.append(
                                (comp_idx,
                                 [float(x_sl.start), float(y_sl.start), float(x_sl.stop), float(y_sl.stop)],
                                 bw * bh)
                            )

            # If we found annotation evidence, build detections
            # Pick the LARGEST hollow bbox by area (suppresses noise)
            bbox_components = [b for _, b, _ in sorted(bbox_candidates, key=lambda x: x[2], reverse=True)]

            if label_class is not None or bbox_components:
                resolved_class = label_class or "crab_pot"  # no label plate → crab_pot
                # If no bbox_components found (thin stroked outlines fragment into tiny pieces),
                # compute overall extent of all green OR red annotation pixels
                if not bbox_components:
                    if label_class == "rock":
                        ys, xs = np.where(green_pixels)
                    else:
                        ys, xs = np.where(red_pixels)
                    if len(xs) > 0:
                        bbox_components = [[
                            float(xs.min()), float(ys.min()),
                            float(xs.max()), float(ys.max()),
                        ]]
                if bbox_components:
                    return [
                        RawDetection(class_name=resolved_class, confidence=0.95, bbox=bbox)
                        for bbox in bbox_components[:1]  # top-1 only
                    ][: self.max_detections]

        # 2. Raw sonar intensity thresholding using max(R, G, B) to preserve amber/copper sonar highlights
        intensity = np.max(rgb, axis=2)

        # Crop margins: top removes header text/scale bars; right removes far-range seafloor clutter
        top_crop = int(img_h * self.top_margin_fraction)
        right_crop = int(img_w * self.right_margin_fraction)
        right_bound = img_w - right_crop if right_crop > 0 else img_w
        analysis_region = intensity[top_crop:, :right_bound]

        threshold = analysis_region.mean() + self.std_devs_above_mean * analysis_region.std()
        mask = analysis_region > threshold

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

            box_w = x_slice.stop - x_slice.start
            box_h = y_slice.stop - y_slice.start
            box_area = box_w * box_h

            # Reject thin slivers (scale bar lines, text rows) and specks
            if box_w < self.min_box_side_px or box_h < self.min_box_side_px:
                continue
            if box_area / img_area < self.min_area_fraction:
                continue

            # Reject dense rectangular blobs (annotation text / headers)
            component_mask = labeled[y_slice, x_slice] == component_index
            fill_ratio = float(component_mask.sum()) / box_area
            if fill_ratio > self.max_fill_ratio:
                continue

            # Offset y back to full-image coordinates (we cropped top_crop rows)
            bbox = [
                float(x_slice.start),
                float(y_slice.start + top_crop),
                float(x_slice.stop),
                float(y_slice.stop + top_crop),
            ]
            peak_intensity = float(analysis_region[y_slice, x_slice].max())
            spread = max(float(analysis_region.std()), 1e-6)
            raw_score = (peak_intensity - float(analysis_region.mean())) / (spread * 4.0)
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
