"""
Uncertainty engine (Phase 10).

Computes a normalized entropy over a classifier's class probabilities:

    H = -sum(p * log2(p)) / log2(n_classes)

which is 0 when the classifier is completely certain (one class at
probability 1) and 1 when it's maximally uncertain (uniform over all
classes) -- e.g. ghost_net=0.52 / natural_seabed=0.43 (spec's own
example) normalizes to a high score with just two classes, exactly as
required.

Thresholds are configurable via `Settings.UNCERTAINTY_*` rather than
hardcoded, per spec section 18.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.models.enums import UncertaintyLevel


@dataclass(slots=True)
class UncertaintyResult:
    score: float  # 0-1, normalized entropy
    level: UncertaintyLevel
    verification_required: bool


def compute_uncertainty(
    probabilities: dict[str, float], settings: Settings | None = None
) -> UncertaintyResult:
    settings = settings or get_settings()

    values = [p for p in probabilities.values() if p > 0]
    n_classes = len(probabilities)

    if n_classes <= 1 or not values:
        score = 0.0
    else:
        entropy = -sum(p * math.log2(p) for p in values)
        max_entropy = math.log2(n_classes)
        score = entropy / max_entropy if max_entropy > 0 else 0.0

    score = max(0.0, min(1.0, score))

    if score >= settings.UNCERTAINTY_HIGH_THRESHOLD:
        level = UncertaintyLevel.HIGH
    elif score >= settings.UNCERTAINTY_MEDIUM_THRESHOLD:
        level = UncertaintyLevel.MEDIUM
    else:
        level = UncertaintyLevel.LOW

    return UncertaintyResult(
        score=round(score, 4),
        level=level,
        verification_required=level is not UncertaintyLevel.LOW,
    )
