from __future__ import annotations

from app.models.enums import (
    GISStatus,
    ModelRunStatus,
    ModelStage,
    PriorityAction,
    RiskLevel,
    TargetClass,
    VerificationMethod,
)
from app.models.priority import PriorityScore
from app.models.risk import RiskScore
from app.models.survey import Survey
from app.models.target import Target
from app.services import mission_service, report_service


def _seed_targets(db):
    survey = Survey(id="survey-1", name="Mission Test Survey")
    db.add(survey)

    # Three targets at increasing distance from the mission start (0,0),
    # with different priority actions so we can check both ranking rules:
    # action-rank first, nearest-neighbor within a rank second.
    targets = [
        Target(id="t-near-later", survey_id="survey-1", classification=TargetClass.ANTHROPOGENIC,
               debris_subclass="other_debris", confidence=0.5, latitude=0.001, longitude=0.001),
        Target(id="t-far-now", survey_id="survey-1", classification=TargetClass.ANTHROPOGENIC,
               debris_subclass="ghost_net", confidence=0.95, latitude=0.02, longitude=0.02),
        Target(id="t-mid-now", survey_id="survey-1", classification=TargetClass.ANTHROPOGENIC,
               debris_subclass="ghost_net", confidence=0.9, latitude=0.01, longitude=0.01),
        Target(id="t-ignored", survey_id="survey-1", classification=TargetClass.NATURAL_SEABED,
               debris_subclass="natural_seabed", confidence=0.99, latitude=0.005, longitude=0.005),
    ]
    for t in targets:
        db.add(t)
    db.commit()

    priorities = {
        "t-near-later": (PriorityAction.VERIFY_LATER, 20.0),
        "t-far-now": (PriorityAction.VERIFY_NOW, 90.0),
        "t-mid-now": (PriorityAction.VERIFY_NOW, 88.0),
        "t-ignored": (PriorityAction.IGNORE, 5.0),
    }
    for target_id, (action, score) in priorities.items():
        db.add(
            PriorityScore(
                target_id=target_id,
                score=score,
                action=action,
                recommended_method=VerificationMethod.AUV_OPTICAL,
                verification_required=action != PriorityAction.IGNORE,
                reasons=["test fixture"],
            )
        )
    db.commit()
    return survey, targets


def test_mission_orders_by_priority_then_nearest(db_session) -> None:
    _seed_targets(db_session)

    mission = mission_service.build_mission(db_session, "survey-1", start_latitude=0.0, start_longitude=0.0)

    assert mission.status.value == "READY"
    # IGNORE target must be excluded entirely.
    stop_ids = [mt.target_id for mt in mission.targets]
    assert "t-ignored" not in stop_ids
    # Both VERIFY_NOW targets come before the VERIFY_LATER target.
    assert set(stop_ids[:2]) == {"t-far-now", "t-mid-now"}
    assert stop_ids[2] == "t-near-later"
    # Within the VERIFY_NOW rank, nearest (t-mid-now) is visited first.
    assert stop_ids[0] == "t-mid-now"
    assert mission.total_distance_m > 0
    assert mission.estimated_duration_s > 0


def test_mission_get_not_found(db_session) -> None:
    from app.core.exceptions import MissionNotFoundError

    try:
        mission_service.get_mission(db_session, "does-not-exist")
        assert False, "expected MissionNotFoundError"
    except MissionNotFoundError:
        pass


def test_report_reflects_full_pipeline_state(db_session) -> None:
    from app.models.environment import EnvironmentContext
    from app.models.risk import RiskScore

    survey, targets = _seed_targets(db_session)

    db_session.add(
        EnvironmentContext(
            target_id="t-far-now",
            reef_status=GISStatus.OK,
            reef_distance_m=12.5,
            inside_reef=False,
            mpa_status=GISStatus.OK,
            inside_mpa=True,
        )
    )
    db_session.add(
        RiskScore(
            target_id="t-far-now",
            score=91.0,
            level=RiskLevel.CRITICAL,
            factors=[{"name": "debris_type", "contribution": 30, "detail": "ghost_net"}],
            weights_version="v1",
        )
    )
    db_session.commit()

    report = report_service.generate_survey_report(db_session, survey)
    assert report.target_count == 4

    row = next(r for r in report.rows if r.target_id == "t-far-now")
    assert row.risk_score == 91.0
    assert row.risk_level == "CRITICAL"
    assert row.priority_action == "VERIFY_NOW"
    assert row.reef_distance_m == 12.5
    assert row.inside_mpa is True

    csv_text = report.to_csv()
    assert "t-far-now" in csv_text
    assert "CRITICAL" in csv_text

    row_ignored = next(r for r in report.rows if r.target_id == "t-ignored")
    assert row_ignored.risk_score is None  # no RiskScore row was ever created for it
