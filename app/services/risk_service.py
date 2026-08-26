"""
Risk engine (Phase 14).

A transparent, additively-weighted score, 0-100, built from five
factors whose weights are read from `Settings` (not hardcoded) and sum
to 100 by construction. Every factor's contribution is stored on the
`RiskScore` row so the frontend/judges can see exactly why a target
scored the way it did -- this is decision support, not a trained
ecological-damage predictor (spec section 23 is explicit that we must
not build one without real labelled ecological-risk data).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.models.enums import RiskLevel
from app.models.environment import EnvironmentContext
from app.models.target import Target

# Relative severity of known debris subclasses, 0-1. `unknown`/anything
# unmapped defaults to a mid-point (0.5) rather than 0, so an unrecognized
# subclass doesn't silently vanish from the score.
_DEBRIS_TYPE_SEVERITY: dict[str, float] = {
    "ghost_net": 1.0,
    "shipwreck": 0.9,
    "metal_debris": 0.7,
    "pipe": 0.6,
    "crab_pot": 0.5,
    "other_debris": 0.4,
    "unknown": 0.3,
}

# Beyond this footprint, size contributes its full weight; below 0 it
# contributes nothing. Linear in between. Configurable via env in a
# later phase if the team wants it -- kept as a module constant for now
# since it's a unit-scale choice, not a policy weight like the others.
_SIZE_SATURATION_M2 = 50.0

# Reef/MPA proximity fall off linearly to zero at this distance.
_PROXIMITY_FALLOFF_M = 200.0


@dataclass(slots=True)
class RiskFactor:
    name: str
    contribution: float
    detail: str


@dataclass(slots=True)
class RiskResult:
    score: float
    level: RiskLevel
    factors: list[RiskFactor]
    weights_version: str


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _debris_type_factor(target: Target, settings: Settings) -> RiskFactor:
    subclass = (target.debris_subclass or "unknown").lower()
    severity = _DEBRIS_TYPE_SEVERITY.get(subclass, 0.5)
    contribution = severity * settings.RISK_WEIGHT_DEBRIS_TYPE
    return RiskFactor("debris_type", round(contribution, 2), f"subclass={subclass}")


def _size_factor(target: Target, settings: Settings) -> RiskFactor:
    if target.estimated_area_m2 is None:
        return RiskFactor("estimated_size", 0.0, "no size estimate available")
    ratio = _clamp01(target.estimated_area_m2 / _SIZE_SATURATION_M2)
    contribution = ratio * settings.RISK_WEIGHT_SIZE
    return RiskFactor(
        "estimated_size", round(contribution, 2), f"area_m2={target.estimated_area_m2:.1f}"
    )


def _reef_proximity_factor(environment: EnvironmentContext | None, settings: Settings) -> RiskFactor:
    if environment is None or environment.reef_status.value not in ("OK", "TEST_FIXTURE"):
        return RiskFactor("reef_proximity", 0.0, "reef GIS not configured")
    if environment.reef_distance_m is None:
        return RiskFactor("reef_proximity", 0.0, "no reef distance available")

    ratio = _clamp01(1.0 - environment.reef_distance_m / _PROXIMITY_FALLOFF_M)
    contribution = ratio * settings.RISK_WEIGHT_REEF_PROXIMITY
    return RiskFactor(
        "reef_proximity", round(contribution, 2), f"distance_m={environment.reef_distance_m:.1f}"
    )


def _protected_area_factor(environment: EnvironmentContext | None, settings: Settings) -> RiskFactor:
    if environment is None or environment.mpa_status.value not in ("OK", "TEST_FIXTURE"):
        return RiskFactor("protected_area", 0.0, "MPA GIS not configured")

    if environment.inside_mpa:
        contribution = settings.RISK_WEIGHT_PROTECTED_AREA
        detail = "inside MPA"
    elif environment.mpa_distance_m is not None:
        ratio = _clamp01(1.0 - environment.mpa_distance_m / _PROXIMITY_FALLOFF_M)
        contribution = ratio * settings.RISK_WEIGHT_PROTECTED_AREA
        detail = f"distance_m={environment.mpa_distance_m:.1f}"
    else:
        contribution = 0.0
        detail = "no MPA distance available"

    return RiskFactor("protected_area", round(contribution, 2), detail)


def _confidence_factor(target: Target, settings: Settings) -> RiskFactor:
    if target.confidence is None:
        return RiskFactor("classification_confidence", 0.0, "no confidence available")
    contribution = _clamp01(target.confidence) * settings.RISK_WEIGHT_CONFIDENCE
    return RiskFactor(
        "classification_confidence", round(contribution, 2), f"confidence={target.confidence:.2f}"
    )


def _level_for_score(score: float, settings: Settings) -> RiskLevel:
    if score >= settings.RISK_LEVEL_CRITICAL_THRESHOLD:
        return RiskLevel.CRITICAL
    if score >= settings.RISK_LEVEL_HIGH_THRESHOLD:
        return RiskLevel.HIGH
    if score >= settings.RISK_LEVEL_MEDIUM_THRESHOLD:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def compute_risk(
    target: Target,
    environment: EnvironmentContext | None,
    settings: Settings | None = None,
) -> RiskResult:
    settings = settings or get_settings()

    factors = [
        _debris_type_factor(target, settings),
        _reef_proximity_factor(environment, settings),
        _protected_area_factor(environment, settings),
        _size_factor(target, settings),
        _confidence_factor(target, settings),
    ]
    score = round(sum(f.contribution for f in factors), 2)
    score = max(0.0, min(100.0, score))

    return RiskResult(
        score=score,
        level=_level_for_score(score, settings),
        factors=factors,
        weights_version=settings.RISK_WEIGHTS_VERSION,
    )
