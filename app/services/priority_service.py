"""
Priority + verification-recommendation service (Phase 15).

Answers "what should the conservation team do about this target right
now" -- distinct from `risk_service`, which only answers "how
ecologically/operationally dangerous is it". Priority also factors in
classification confidence/uncertainty: a CRITICAL-risk target with high
classification uncertainty still needs eyes on it even though we're not
sure what it is yet, while a high-confidence natural-seabed call is
safe to skip regardless of size or reef proximity.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.models.enums import PriorityAction, TargetClass, UncertaintyLevel, VerificationMethod
from app.models.target import Target
from app.services.risk_service import RiskResult


@dataclass(slots=True)
class PriorityResult:
    score: float
    action: PriorityAction
    recommended_method: VerificationMethod
    verification_required: bool
    reasons: list[str]


def _uncertainty_level(target: Target, settings: Settings) -> UncertaintyLevel:
    if target.uncertainty is None:
        return UncertaintyLevel.HIGH  # unknown uncertainty is treated conservatively
    if target.uncertainty >= settings.UNCERTAINTY_HIGH_THRESHOLD:
        return UncertaintyLevel.HIGH
    if target.uncertainty >= settings.UNCERTAINTY_MEDIUM_THRESHOLD:
        return UncertaintyLevel.MEDIUM
    return UncertaintyLevel.LOW


def compute_priority(
    target: Target, risk: RiskResult, settings: Settings | None = None
) -> PriorityResult:
    settings = settings or get_settings()
    uncertainty_level = _uncertainty_level(target, settings)
    reasons: list[str] = [f"risk={risk.level.value}", f"uncertainty={uncertainty_level.value}"]

    is_confident_natural = (
        target.classification is TargetClass.NATURAL_SEABED
        and target.confidence is not None
        and target.confidence >= settings.PRIORITY_IGNORE_CONFIDENCE_THRESHOLD
        and uncertainty_level is UncertaintyLevel.LOW
    )

    if is_confident_natural:
        reasons.append(f"confidence={target.confidence:.2f} >= ignore threshold")
        return PriorityResult(
            score=risk.score,
            action=PriorityAction.IGNORE,
            recommended_method=VerificationMethod.NONE,
            verification_required=False,
            reasons=reasons,
        )

    # Uncertainty nudges the score up slightly: two targets with identical
    # risk but different classification confidence should not rank
    # identically -- the less-certain one deserves earlier attention.
    score = min(100.0, risk.score + uncertainty_level_bump(uncertainty_level))

    if risk.score >= settings.PRIORITY_VERIFY_NOW_RISK_THRESHOLD:
        action = PriorityAction.VERIFY_NOW
        method = VerificationMethod.ROV_CAMERA if uncertainty_level is UncertaintyLevel.HIGH else VerificationMethod.AUV_OPTICAL
        reasons.append(f"risk_score={risk.score:.1f} >= verify-now threshold")
        verification_required = True
    elif risk.score >= settings.PRIORITY_VERIFY_NEXT_RISK_THRESHOLD:
        action = PriorityAction.VERIFY_NEXT
        method = VerificationMethod.AUV_OPTICAL
        reasons.append(f"risk_score={risk.score:.1f} >= verify-next threshold")
        verification_required = True
    else:
        action = PriorityAction.VERIFY_LATER
        method = VerificationMethod.MANUAL_REVIEW
        verification_required = uncertainty_level is not UncertaintyLevel.LOW
        reasons.append(f"risk_score={risk.score:.1f} below verify-next threshold")

    return PriorityResult(
        score=round(score, 2),
        action=action,
        recommended_method=method,
        verification_required=verification_required,
        reasons=reasons,
    )


def uncertainty_level_bump(level: UncertaintyLevel) -> float:
    return {UncertaintyLevel.LOW: 0.0, UncertaintyLevel.MEDIUM: 5.0, UncertaintyLevel.HIGH: 10.0}[level]
