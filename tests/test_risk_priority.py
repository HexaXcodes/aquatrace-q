from __future__ import annotations

from app.models.enums import GISStatus, TargetClass
from app.models.environment import EnvironmentContext
from app.models.target import Target
from app.services import priority_service, risk_service


def _target(**overrides) -> Target:
    defaults = dict(
        id="t1",
        survey_id="s1",
        classification=TargetClass.ANTHROPOGENIC,
        debris_subclass="ghost_net",
        confidence=0.9,
        uncertainty=0.1,
        estimated_area_m2=40.0,
    )
    defaults.update(overrides)
    return Target(**defaults)


def test_risk_score_high_for_ghost_net_near_reef_in_mpa() -> None:
    target = _target()
    environment = EnvironmentContext(
        target_id="t1",
        reef_status=GISStatus.OK,
        reef_distance_m=5.0,
        inside_reef=False,
        mpa_status=GISStatus.OK,
        inside_mpa=True,
    )

    result = risk_service.compute_risk(target, environment)
    assert result.level.value in ("HIGH", "CRITICAL")
    assert result.score > 60
    factor_names = {f.name for f in result.factors}
    assert factor_names == {
        "debris_type",
        "reef_proximity",
        "protected_area",
        "estimated_size",
        "classification_confidence",
    }


def test_risk_score_low_when_gis_not_configured_and_small_low_confidence() -> None:
    target = _target(debris_subclass="unknown", confidence=0.2, estimated_area_m2=1.0)
    result = risk_service.compute_risk(target, environment=None)
    assert result.level.value == "LOW"
    assert result.score < 30


def test_priority_ignore_for_confident_natural_seabed() -> None:
    target = _target(
        classification=TargetClass.NATURAL_SEABED,
        debris_subclass="natural_seabed",
        confidence=0.97,
        uncertainty=0.05,
    )
    risk_result = risk_service.compute_risk(target, environment=None)
    priority_result = priority_service.compute_priority(target, risk_result)

    assert priority_result.action.value == "IGNORE"
    assert priority_result.recommended_method.value == "NONE"
    assert priority_result.verification_required is False


def test_priority_verify_now_for_high_risk_high_uncertainty() -> None:
    target = _target(uncertainty=0.9)
    environment = EnvironmentContext(
        target_id="t1", reef_status=GISStatus.OK, reef_distance_m=2.0, inside_reef=True,
        mpa_status=GISStatus.OK, inside_mpa=True,
    )
    risk_result = risk_service.compute_risk(target, environment)
    priority_result = priority_service.compute_priority(target, risk_result)

    assert priority_result.action.value == "VERIFY_NOW"
    assert priority_result.recommended_method.value == "ROV_CAMERA"
    assert priority_result.verification_required is True
    assert any("uncertainty=HIGH" in r for r in priority_result.reasons)
