"""
`E004ShipwreckDetector` -- adapts the trained E004 Compact U-Net
(binary shipwreck segmentation) to the `DetectionModel` interface.

Why `DetectionModel` and not `SegmentationModel`: `SegmentationModel` is
defined in `app/ml/base.py` but `model_registry.get_segmentation_model()`
is never called by `processing_service`'s DETECTING stage --
`detection_service.run_detection()` only ever calls
`get_detection_model()`. Rather than adding a new orchestration stage,
this class runs the U-Net internally and converts its output mask into
one or more `RawDetection`s (bbox + mask_path), the same shape
`FixtureThresholdDetector` already produces. See
`docs/ml-integration.md` for the full writeup, including the small-
shipwreck accuracy caveat and the tiling strategy below.

Preprocessing note: `E004_AADVIK_HANDOFF/src/training/dataset.py` (the
authoritative source for how E004 was trained) does *not* contain a
resize/pad strategy -- it only accepts pre-tiled, exact 1024x1024
image/mask pairs and normalizes via `/255.0`. Real uploaded sonar images
are arbitrary sizes, so *some* strategy for getting to 1024x1024 has to
be invented at inference time; nothing in the handoff package specifies
one. Downsampling a whole large image to 1024x1024 would shrink
shipwreck shapes to a different apparent scale than the native-resolution
tiles E004 was trained on, so this implementation instead tiles the
input into non-overlapping 1024x1024 windows (zero-padding the final
row/column of tiles if needed) and stitches per-tile detections back into
original-image pixel coordinates. This preserves native pixel scale but
means an object straddling a tile boundary can be split into two
detections -- a known limitation, documented in `docs/ml-integration.md`
alongside the small-shipwreck weakness.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from app.core.config import get_settings
from app.ml.base import DetectionModel, RawDetection

_TILE_SIZE = 1024


class TorchUnavailableError(RuntimeError):
    """Raised when torch is not importable in this environment."""


class E004ShipwreckDetector(DetectionModel):
    model_name = "e004-unet-shipwreck-segmentation"
    model_version = "E004"

    def __init__(
        self,
        checkpoint_path: Path,
        *,
        mask_threshold: float = 0.6,
        min_component_pixels: int = 800,
        max_detections: int = 20,
    ) -> None:
        try:
            import torch

            from app.ml.e004_unet import UNet
        except ImportError as exc:  # pragma: no cover - exercised only when torch uninstalled
            raise TorchUnavailableError(
                "torch is not importable in this environment. Install it (CPU wheel: "
                "`pip install torch --index-url https://download.pytorch.org/whl/cpu`) "
                "per requirements.txt."
            ) from exc

        self._torch = torch
        self.mask_threshold = mask_threshold
        self.min_component_pixels = min_component_pixels
        self.max_detections = max_detections

        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        state_dict = checkpoint["model_state_dict"] if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint else checkpoint

        model = UNet(in_channels=1, out_channels=1)
        model.load_state_dict(state_dict)
        model.eval()
        self._model = model

    def predict(self, image_path: Path) -> list[RawDetection]:
        with Image.open(image_path) as img:
            gray = np.asarray(img.convert("L"), dtype=np.float32)

        height, width = gray.shape
        detections: list[RawDetection] = []

        for y0 in range(0, height, _TILE_SIZE):
            for x0 in range(0, width, _TILE_SIZE):
                tile_h = min(_TILE_SIZE, height - y0)
                tile_w = min(_TILE_SIZE, width - x0)
                detections.extend(
                    self._predict_tile(gray, image_path, x0, y0, tile_w, tile_h)
                )

        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections[: self.max_detections]

    def _predict_tile(
        self, gray: np.ndarray, image_path: Path, x0: int, y0: int, tile_w: int, tile_h: int
    ) -> list[RawDetection]:
        torch = self._torch

        canvas = np.zeros((_TILE_SIZE, _TILE_SIZE), dtype=np.float32)
        canvas[:tile_h, :tile_w] = gray[y0 : y0 + tile_h, x0 : x0 + tile_w]

        input_tensor = torch.from_numpy(canvas / 255.0).unsqueeze(0).unsqueeze(0)
        with torch.no_grad():
            logits = self._model(input_tensor)
        probabilities = torch.sigmoid(logits)[0, 0].numpy()

        binary_mask = probabilities > self.mask_threshold
        # Only the real (non-padded) region of this tile is eligible -- the
        # zero-padded border is an artifact of tiling, not real sonar
        # content, and the model was never trained on that edge.
        valid = np.zeros_like(binary_mask)
        valid[:tile_h, :tile_w] = True
        binary_mask &= valid

        if not binary_mask.any():
            return []

        labeled, num_components = ndimage.label(binary_mask)
        if num_components == 0:
            return []

        component_sizes = ndimage.sum(binary_mask, labeled, index=range(1, num_components + 1))
        slices = ndimage.find_objects(labeled)

        results: list[RawDetection] = []
        for component_index, size in enumerate(component_sizes, start=1):
            if size < self.min_component_pixels:
                continue
            y_slice, x_slice = slices[component_index - 1]
            component_mask = labeled[y_slice, x_slice] == component_index

            confidence = float(np.clip(probabilities[y_slice, x_slice][component_mask].mean(), 0.0, 1.0))
            bbox = [
                float(x_slice.start + x0),
                float(y_slice.start + y0),
                float(x_slice.stop + x0),
                float(y_slice.stop + y0),
            ]
            mask_path = self._save_mask_crop(component_mask, image_path)

            results.append(
                RawDetection(class_name="shipwreck", confidence=confidence, bbox=bbox, mask_path=str(mask_path))
            )
        return results

    def _save_mask_crop(self, component_mask: np.ndarray, image_path: Path) -> Path:
        settings = get_settings()
        mask_dir = settings.OUTPUT_DIRECTORY / "e004_masks"
        mask_dir.mkdir(parents=True, exist_ok=True)

        mask_image = Image.fromarray((component_mask * 255).astype(np.uint8), mode="L")
        mask_filename = f"{image_path.stem}_{uuid.uuid4().hex[:12]}.png"
        mask_path = mask_dir / mask_filename
        mask_image.save(mask_path)
        return mask_path
