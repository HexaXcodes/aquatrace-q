"""
FeatureExtractor (Phase 7).

`StatisticalFeatureExtractor` computes real, deterministic features
from the target's crop of the sonar image: intensity statistics,
texture (via local variance), shape (bbox aspect ratio, extent), and a
simple shadow-proxy (dark-region fraction below the bright core). These
are genuine numbers computed from real pixels -- not placeholders.

It deliberately does NOT attempt a CNN embedding: that requires a
trained network the ML team owns. `FeatureExtractor` is the interface
they implement against (e.g. `PyTorchEmbeddingExtractor`) to append
learned features alongside or instead of these hand-engineered ones --
`feature_version` distinguishes the two so nothing downstream conflates
them.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass(slots=True)
class ExtractedFeatures:
    feature_version: str
    values: list[float]
    names: list[str]


class FeatureExtractor(abc.ABC):
    feature_version: str = "unregistered"

    @abc.abstractmethod
    def extract(self, image_path: Path, bbox: list[float] | None) -> ExtractedFeatures:
        raise NotImplementedError


class StatisticalFeatureExtractor(FeatureExtractor):
    """Hand-engineered features computed directly from the sonar image crop.

    This is a real, currently-registered implementation (not a stub) --
    it is simply not a learned representation. See module docstring for
    where a CNN-embedding extractor plugs in alongside it.
    """

    feature_version = "stat-v1"

    def extract(self, image_path: Path, bbox: list[float] | None) -> ExtractedFeatures:
        with Image.open(image_path) as img:
            gray = np.asarray(img.convert("L"), dtype=np.float32)

        crop = self._crop(gray, bbox)
        if crop.size == 0:
            crop = gray  # bbox degenerate/out of range -- fall back to full frame

        intensity_mean = float(crop.mean())
        intensity_std = float(crop.std())
        intensity_max = float(crop.max())
        intensity_min = float(crop.min())

        # Texture proxy: local variance via a simple 3x3 sliding window,
        # summarized as its mean -- higher for cluttered/textured regions,
        # lower for smooth sand/mud.
        texture_score = float(self._local_variance(crop).mean())

        height, width = crop.shape[:2]
        aspect_ratio = float(width / height) if height else 0.0
        extent = float(width * height)

        # Shadow proxy: fraction of the crop darker than half the local
        # mean, a rough stand-in for acoustic shadow until a proper
        # shadow-geometry feature is supplied by the ML team.
        shadow_fraction = float(np.mean(crop < (intensity_mean * 0.5))) if intensity_mean else 0.0

        values = [
            intensity_mean,
            intensity_std,
            intensity_max,
            intensity_min,
            texture_score,
            aspect_ratio,
            extent,
            shadow_fraction,
        ]
        names = [
            "intensity_mean",
            "intensity_std",
            "intensity_max",
            "intensity_min",
            "texture_score",
            "aspect_ratio",
            "extent",
            "shadow_fraction",
        ]
        return ExtractedFeatures(feature_version=self.feature_version, values=values, names=names)

    @staticmethod
    def _crop(gray: np.ndarray, bbox: list[float] | None) -> np.ndarray:
        if bbox is None:
            return gray
        x1, y1, x2, y2 = bbox
        height, width = gray.shape[:2]
        x1c, x2c = sorted((max(0, int(x1)), min(width, int(x2))))
        y1c, y2c = sorted((max(0, int(y1)), min(height, int(y2))))
        return gray[y1c:y2c, x1c:x2c]

    @staticmethod
    def _local_variance(crop: np.ndarray, window: int = 3) -> np.ndarray:
        if crop.shape[0] < window or crop.shape[1] < window:
            return np.array([float(crop.var())])

        # Sliding-window mean/mean-of-squares via cumulative sums --
        # avoids an explicit per-pixel Python loop.
        shape = (crop.shape[0] - window + 1, crop.shape[1] - window + 1, window, window)
        strides = crop.strides * 2
        windows = np.lib.stride_tricks.as_strided(crop, shape=shape, strides=strides)
        return windows.var(axis=(2, 3))
