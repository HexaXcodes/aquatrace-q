from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import create_uploaded_survey


def test_run_detection_and_list(client: TestClient) -> None:
    survey = create_uploaded_survey(client, "Detection Test Survey")

    from app.db.session import get_session_factory
    from app.models.survey import Survey
    from app.services import detection_service

    db = get_session_factory()()
    try:
        survey_row = db.get(Survey, survey["id"])
        detections = detection_service.run_detection(db, survey_row)
    finally:
        db.close()

    assert len(detections) >= 1
    assert all(d.model_name == "fixture-threshold-detector" for d in detections)
    assert all(0.0 <= d.confidence <= 1.0 for d in detections)

    response = client.get(f"/api/v1/surveys/{survey['id']}/detections")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(detections)


def test_targets_created_from_detections(client: TestClient) -> None:
    survey = create_uploaded_survey(client, "Target Creation Survey")

    from app.db.session import get_session_factory
    from app.models.survey import Survey
    from app.services import detection_service, target_service

    db = get_session_factory()()
    try:
        survey_row = db.get(Survey, survey["id"])
        detections = detection_service.run_detection(db, survey_row)
        targets = target_service.create_targets_from_detections(db, detections)
    finally:
        db.close()

    assert len(targets) == len(detections)
    for target in targets:
        assert target.classification.value == "ANTHROPOGENIC"
        assert target.bbox is not None

    response = client.get(f"/api/v1/surveys/{survey['id']}/targets")
    assert response.status_code == 200
    assert response.json()["total"] == len(targets)


def test_get_target_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/targets/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"] == "TargetNotFoundError"
