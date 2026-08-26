"""
Phase 18/21 end-to-end integration test.

Drives the pipeline entirely through the public API -- upload, process,
poll job status, then read back detections/targets/classification/
environment/risk/priority/report -- verifying the data contract between
every stage, exactly as spec section 21 requires. Uses the real fixture
detector, real feature extractor, real (untrained, hence NOT_TRAINED)
classifiers, and the real GIS NullProvider -- nothing here is a mocked
API response.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import create_uploaded_survey


def test_full_pipeline_end_to_end(client: TestClient) -> None:
    survey = create_uploaded_survey(
        client, "E2E Pipeline Survey", origin_latitude=12.9, origin_longitude=74.8, meters_per_pixel=0.05
    )
    survey_id = survey["id"]

    # --- Kick off processing ------------------------------------------------
    process_response = client.post(
        f"/api/v1/surveys/{survey_id}/process",
        json={"start_latitude": 12.9, "start_longitude": 74.8},
    )
    assert process_response.status_code == 202
    job = process_response.json()
    assert job["status"] in (
        "QUEUED", "VALIDATING", "PREPROCESSING", "DETECTING", "CLASSIFYING",
        "QML_CLASSIFYING", "GEOLOCATING", "GIS_ENRICHMENT", "RISK_SCORING",
        "PRIORITIZING", "MISSION_PLANNING", "REPORTING", "COMPLETED",
    )

    # BackgroundTasks run synchronously within the TestClient's request/
    # response cycle, so by the time we get a response the job should
    # already be finished (or failed, if there's a real bug to catch).
    job_response = client.get(f"/api/v1/jobs/{job['id']}")
    assert job_response.status_code == 200
    job_final = job_response.json()
    assert job_final["status"] == "COMPLETED", job_final.get("error_message") or job_final["stage_log"]

    stage_names = [entry["stage"] for entry in job_final["stage_log"]]
    for expected_stage in [
        "VALIDATING", "PREPROCESSING", "DETECTING", "CLASSIFYING", "QML_CLASSIFYING",
        "GEOLOCATING", "GIS_ENRICHMENT", "RISK_SCORING", "PRIORITIZING",
        "MISSION_PLANNING", "REPORTING", "COMPLETED",
    ]:
        assert expected_stage in stage_names, f"missing stage {expected_stage} in {stage_names}"

    # --- Detections + targets -------------------------------------------------
    detections = client.get(f"/api/v1/surveys/{survey_id}/detections").json()
    assert detections["total"] >= 1

    targets = client.get(f"/api/v1/surveys/{survey_id}/targets").json()
    assert targets["total"] == detections["total"]
    target_id = targets["items"][0]["id"]

    # --- Classification: honest NOT_TRAINED / NOT_TRAINED-or-UNAVAILABLE ------
    classification = client.get(f"/api/v1/targets/{target_id}/classification").json()
    assert classification["target_id"] == target_id
    stages_seen = {r["stage"] for r in classification["records"]}
    assert stages_seen == {"CLASSICAL", "QUANTUM"}
    for record in classification["records"]:
        if record["stage"] == "CLASSICAL":
            assert record["run_status"] == "NOT_TRAINED"
            assert record["predicted_class"] is None
        else:
            assert record["run_status"] in ("NOT_TRAINED", "UNAVAILABLE")
            assert record["predicted_class"] is None

    # --- Geolocation: target should have real coordinates from the survey
    # transform (origin + meters_per_pixel were supplied at upload time) ------
    target_detail = client.get(f"/api/v1/targets/{target_id}").json()
    assert target_detail["latitude"] is not None
    assert target_detail["longitude"] is not None
    assert target_detail["coordinate_source"] == "SURVEY_TRANSFORM"

    # --- Environment: GIS not configured in this test environment -> honest
    # NOT_CONFIGURED, never a fabricated reef/MPA distance ---------------------
    environment = client.get(f"/api/v1/targets/{target_id}/environment").json()
    assert environment["reef_status"] == "NOT_CONFIGURED"
    assert environment["reef_distance_m"] is None
    assert environment["mpa_status"] == "NOT_CONFIGURED"

    # --- Risk + priority: computed even with classification NOT_TRAINED and
    # GIS NOT_CONFIGURED -- every factor just contributes 0 where genuinely
    # unavailable, rather than the stage being skipped entirely -----------------
    risk = client.get(f"/api/v1/targets/{target_id}/risk").json()
    assert risk["target_id"] == target_id
    assert 0.0 <= risk["score"] <= 100.0
    assert risk["level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    priority = client.get(f"/api/v1/targets/{target_id}/priority").json()
    assert priority["target_id"] == target_id
    assert priority["action"] in ("VERIFY_NOW", "VERIFY_NEXT", "VERIFY_LATER", "IGNORE")

    # --- Mission: built automatically because start_lat/lon were supplied
    # to /process --------------------------------------------------------------
    mission_stage = next(e for e in job_final["stage_log"] if e["stage"] == "MISSION_PLANNING")
    assert mission_stage["status"] == "OK"

    # --- Report: JSON + CSV both reproducible from DB state --------------------
    report_json = client.get(f"/api/v1/surveys/{survey_id}/report").json()
    assert report_json["target_count"] == targets["total"]
    report_row = next(r for r in report_json["targets"] if r["target_id"] == target_id)
    assert report_row["risk_score"] == risk["score"]
    assert report_row["priority_action"] == priority["action"]

    report_csv = client.get(f"/api/v1/surveys/{survey_id}/report.csv")
    assert report_csv.status_code == 200
    assert target_id in report_csv.text


def test_process_unknown_survey_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/surveys/does-not-exist/process",
        json={"start_latitude": 0.0, "start_longitude": 0.0},
    )
    assert response.status_code == 404


def test_job_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/jobs/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"] == "JobNotFoundError"


def test_process_survey_without_upload_fails_gracefully(client: TestClient) -> None:
    create_response = client.post("/api/v1/surveys", json={"name": "No File Survey"})
    survey_id = create_response.json()["id"]

    process_response = client.post(
        f"/api/v1/surveys/{survey_id}/process", json={}
    )
    assert process_response.status_code == 202  # job accepted; failure surfaces via job status

    job_id = process_response.json()["id"]
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "FAILED"
    assert "no uploaded file" in job["error_message"].lower()
