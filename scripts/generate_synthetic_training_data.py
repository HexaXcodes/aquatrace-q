"""
Generates a small synthetic labelled dataset in the same 8-feature shape
StatisticalFeatureExtractor produces, so the training pipeline can be
proven correct before real labelled sonar data exists.

Feature ranges below are not [0, 1]-normalized -- they're centered on the
real value ranges StatisticalFeatureExtractor actually outputs (checked
directly against a live pipeline run: intensity values are raw 0-255
pixel statistics, extent is a raw pixel-area bbox size, etc.). A
classifier trained on mismatched-scale synthetic data would produce
garbage the moment it's asked to classify a real feature vector from the
running app, which would defeat the actual point of this exercise.

Usage:
    python scripts/generate_synthetic_training_data.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

FEATURE_NAMES = [
    "intensity_mean",
    "intensity_std",
    "intensity_max",
    "intensity_min",
    "texture_score",
    "aspect_ratio",
    "extent",
    "shadow_fraction",
]

# loc/scale per feature, in the same order as FEATURE_NAMES. Chosen to be
# clearly separable and roughly plausible per class, not derived from any
# real dataset -- natural_seabed is low-intensity/low-texture/square,
# ghost_net is bright/textured/elongated with a strong shadow, metal_debris
# is bright/compact/smoother with a smaller shadow than a tangled net.
CLASS_PROFILES: dict[str, dict[str, list[float]]] = {
    "natural_seabed": {
        "loc": [95, 10, 130, 70, 20, 1.0, 900, 0.05],
        "scale": [5, 2, 8, 5, 4, 0.15, 150, 0.02],
    },
    "ghost_net": {
        "loc": [180, 25, 240, 140, 55, 2.2, 500, 0.30],
        "scale": [10, 5, 10, 15, 10, 0.4, 120, 0.05],
    },
    "metal_debris": {
        "loc": [200, 15, 250, 160, 35, 1.3, 700, 0.15],
        "scale": [10, 4, 8, 12, 8, 0.25, 130, 0.04],
    },
}

SAMPLES_PER_CLASS = 20
OUTPUT_PATH = Path("data/synthetic_training_data.csv")
SEED = 42


def make_class_rows(
    label: str, loc: list[float], scale: list[float], n: int, rng: np.random.Generator
) -> list[list]:
    features = rng.normal(loc=loc, scale=scale, size=(n, len(FEATURE_NAMES)))
    # Keep values in physically sensible ranges: no negative intensities,
    # aspect_ratio/extent/shadow_fraction can't go negative either.
    features = np.clip(features, 0.0, None)
    return [[*row.round(3).tolist(), label] for row in features]


def main() -> None:
    rng = np.random.default_rng(SEED)

    rows: list[list] = []
    for label, profile in CLASS_PROFILES.items():
        rows.extend(
            make_class_rows(label, profile["loc"], profile["scale"], SAMPLES_PER_CLASS, rng)
        )

    rng.shuffle(rows)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([*FEATURE_NAMES, "label"])
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows ({len(CLASS_PROFILES)} classes) to {OUTPUT_PATH}")
    print(f"Classes: {sorted(CLASS_PROFILES)}")


if __name__ == "__main__":
    main()
