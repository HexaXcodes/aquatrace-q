from __future__ import annotations

from fastapi.testclient import TestClient


def _toy_samples(n_per_class: int = 8):
    samples = []
    for i in range(n_per_class):
        samples.append({"features": [0.1 + 0.01 * i, 0.2, 0.15, 0.05], "label": "natural_seabed"})
        samples.append({"features": [0.9 - 0.01 * i, 0.8, 0.85, 0.95], "label": "ghost_net"})
    return samples


def test_classification_experiment_end_to_end(client: TestClient) -> None:
    payload = {
        "dataset_version": "test-fixture-v1",
        "feature_version": "stat-v1",
        "samples": _toy_samples(),
        "test_size": 0.25,
    }
    response = client.post("/api/v1/experiments/classification", json=payload)
    assert response.status_code == 201

    body = response.json()
    assert body["sample_count"] == 16
    assert body["classical_status"] == "OK"
    assert body["classical_metrics"]["accuracy"] >= 0.0
    assert body["quantum_status"] in ("OK", "UNAVAILABLE")
    if body["quantum_status"] == "OK":
        assert body["quantum_metrics"]["accuracy"] >= 0.0
    else:
        assert body["quantum_metrics"] is None

    get_response = client.get(f"/api/v1/experiments/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == body["id"]


def test_experiment_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/experiments/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"] == "ExperimentNotFoundError"


def test_experiment_requires_at_least_two_classes(client: TestClient) -> None:
    payload = {
        "dataset_version": "bad-fixture",
        "feature_version": "stat-v1",
        "samples": [{"features": [0.1, 0.2, 0.1, 0.1], "label": "only_one_class"}] * 6,
    }
    response = client.post("/api/v1/experiments/classification", json=payload)
    assert response.status_code == 400
