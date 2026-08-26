from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import create_uploaded_survey


def test_geolocate_target_with_full_metadata(client: TestClient) -> None:
    survey = create_uploaded_survey(
        client, "Geolocation Survey", origin_latitude=12.9, origin_longitude=74.8, meters_per_pixel=0.1
    )

    from app.db.session import get_session_factory
    from app.models.survey import Survey
    from app.services import coordinate_service, detection_service, target_service

    db = get_session_factory()()
    try:
        survey_row = db.get(Survey, survey["id"])
        detections = detection_service.run_detection(db, survey_row)
        targets = target_service.create_targets_from_detections(db, detections)
        target = targets[0]
        result = coordinate_service.geolocate_target(survey_row, target)
    finally:
        db.close()

    assert result.source.value == "SURVEY_TRANSFORM"
    # Origin is (12.9, 74.8); a pixel offset south+east should move us to
    # slightly lower latitude and slightly higher longitude.
    assert result.latitude < 12.9
    assert result.longitude > 74.8


def test_geolocate_target_without_metadata_returns_none() -> None:
    from app.models.enums import TargetClass
    from app.models.survey import Survey
    from app.models.target import Target
    from app.services import coordinate_service

    survey = Survey(id="s1", name="No Metadata Survey", meters_per_pixel=None)
    target = Target(id="t1", survey_id="s1", classification=TargetClass.ANTHROPOGENIC, bbox=[0, 0, 10, 10])

    result = coordinate_service.geolocate_target(survey, target)
    assert result.latitude is None
    assert result.longitude is None
    assert result.source is None
    assert "meters_per_pixel" in result.note or "origin" in result.note
