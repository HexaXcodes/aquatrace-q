"""Shared test helpers: build a real uploaded survey with a synthetic
sonar-like image containing a few bright "targets" for the fixture
detector to find."""

from __future__ import annotations

import io

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image


def synthetic_sonar_png(width: int = 200, height: int = 150, n_blobs: int = 3) -> io.BytesIO:
    """A grayscale image: uniform dark background with a few bright
    square 'blobs' -- exactly the kind of signal FixtureThresholdDetector
    is designed to find via intensity thresholding."""
    rng = np.random.default_rng(7)
    background = rng.normal(loc=60, scale=5, size=(height, width)).clip(0, 255).astype(np.uint8)

    for i in range(n_blobs):
        cx = 20 + i * 50
        cy = 30 + i * 20
        size = 10
        background[cy : cy + size, cx : cx + size] = 220

    image = Image.fromarray(background, mode="L")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def create_uploaded_survey(
    client: TestClient,
    name: str = "Test Survey",
    *,
    origin_latitude: float = 12.9,
    origin_longitude: float = 74.8,
    meters_per_pixel: float = 0.05,
) -> dict:
    """Create a survey and upload a synthetic sonar image with enough
    metadata for geolocation to work. Returns the SurveyRead JSON dict."""
    create_response = client.post("/api/v1/surveys", json={"name": name})
    assert create_response.status_code == 201
    survey = create_response.json()

    upload_response = client.post(
        f"/api/v1/surveys/{survey['id']}/upload",
        files={"file": ("sonar.png", synthetic_sonar_png(), "image/png")},
        data={
            "origin_latitude": str(origin_latitude),
            "origin_longitude": str(origin_longitude),
            "meters_per_pixel": str(meters_per_pixel),
            "sensor_name": "Klein 3000 (test fixture)",
        },
    )
    assert upload_response.status_code == 200
    return upload_response.json()
