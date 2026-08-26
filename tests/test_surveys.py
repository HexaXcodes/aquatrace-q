from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image


def _fake_sonar_png(width: int = 256, height: int = 128) -> io.BytesIO:
    image = Image.new("L", (width, height), color=128)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_survey(client: TestClient) -> None:
    response = client.post("/api/v1/surveys", json={"name": "Hebbal Reef Pass 1"})
    assert response.status_code == 201

    body = response.json()
    assert body["name"] == "Hebbal Reef Pass 1"
    assert body["status"] == "CREATED"
    assert body["file_path"] is None
    assert body["width"] is None


def test_create_survey_rejects_empty_name(client: TestClient) -> None:
    response = client.post("/api/v1/surveys", json={"name": ""})
    assert response.status_code == 422


def test_get_survey_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/surveys/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"] == "SurveyNotFoundError"


def test_full_ingestion_flow(client: TestClient) -> None:
    create_response = client.post("/api/v1/surveys", json={"name": "Hebbal Reef Pass 2"})
    survey_id = create_response.json()["id"]

    upload_response = client.post(
        f"/api/v1/surveys/{survey_id}/upload",
        files={"file": ("sonar_pass_2.png", _fake_sonar_png(320, 180), "image/png")},
        data={"sensor_name": "Klein 3000", "meters_per_pixel": "0.05"},
    )
    assert upload_response.status_code == 200

    body = upload_response.json()
    assert body["status"] == "UPLOADED"
    assert body["file_type"] == "png"
    assert body["width"] == 320
    assert body["height"] == 180
    assert body["sensor_name"] == "Klein 3000"
    assert body["meters_per_pixel"] == 0.05
    # Never fabricated: no CRS/lat/lon was supplied, so these stay null.
    assert body["coordinate_reference_system"] is None
    assert body["origin_latitude"] is None

    get_response = client.get(f"/api/v1/surveys/{survey_id}")
    assert get_response.status_code == 200
    assert get_response.json()["width"] == 320


def test_upload_rejects_unsupported_extension(client: TestClient) -> None:
    create_response = client.post("/api/v1/surveys", json={"name": "Bad Upload Survey"})
    survey_id = create_response.json()["id"]

    response = client.post(
        f"/api/v1/surveys/{survey_id}/upload",
        files={"file": ("raw_dump.xtf", io.BytesIO(b"not a real xtf"), "application/octet-stream")},
    )
    assert response.status_code == 415
    assert response.json()["error"] == "UnsupportedSonarFormatError"


def test_upload_rejects_corrupt_image(client: TestClient) -> None:
    create_response = client.post("/api/v1/surveys", json={"name": "Corrupt Upload Survey"})
    survey_id = create_response.json()["id"]

    response = client.post(
        f"/api/v1/surveys/{survey_id}/upload",
        files={"file": ("sonar.png", io.BytesIO(b"this is not png data"), "image/png")},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "InvalidSonarFileError"


def test_list_surveys(client: TestClient) -> None:
    client.post("/api/v1/surveys", json={"name": "Survey A"})
    client.post("/api/v1/surveys", json={"name": "Survey B"})

    response = client.get("/api/v1/surveys", params={"limit": 10, "offset": 0})
    assert response.status_code == 200

    body = response.json()
    assert body["total"] >= 2
    assert len(body["items"]) >= 2
