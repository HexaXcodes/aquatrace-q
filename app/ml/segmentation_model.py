"""
Segmentation model integration point (Phase 6).

`SegmentationModel` is fully defined in `app/ml/base.py`. No fixture
implementation is provided here: unlike detection (where a crude
threshold-based fixture is a legitimate, honestly-labelled stand-in),
producing a *mask* without a real trained model would mean fabricating
pixel-level segmentation data, which spec section "NO FAKE SCIENCE"
explicitly rules out.

`model_registry.get_segmentation_model()` therefore returns `None`
until Shaun/Shashank register a real `SegmentationModel` implementation
here and in `app/ml/model_registry.py`. Services that call it must
handle `None` as "segmentation unavailable", not silently skip the
check.
"""

from __future__ import annotations

from app.ml.base import RawDetection, SegmentationModel  # noqa: F401

__all__ = ["SegmentationModel", "RawDetection"]
