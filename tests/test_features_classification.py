from __future__ import annotations

import numpy as np
from fastapi.testclient import TestClient

from tests.helpers import create_uploaded_survey


def _make_target(db, survey_row):
    from app.services import detection_service, target_service

    detections = detection_service.run_detection(db, survey_row)
    targets = target_service.create_targets_from_detections(db, detections)
    return targets[0]


def test_feature_extraction_produces_real_values(client: TestClient) -> None:
    survey = create_uploaded_survey(client, "Feature Extraction Survey")

    from app.db.session import get_session_factory
    from app.models.survey import Survey
    from app.services import feature_service

    db = get_session_factory()()
    try:
        survey_row = db.get(Survey, survey["id"])
        target = _make_target(db, survey_row)
        feature_vector = feature_service.extract_and_store_features(db, target, survey_row)
    finally:
        db.close()

    assert feature_vector.feature_version == "stat-v1"
    assert feature_vector.dimensions == len(feature_vector.values)
    assert feature_vector.dimensions == 8
    # Real numbers, not placeholders -- the target's bbox sits exactly on
    # the bright blob we painted into the synthetic image, so its crop
    # should read as uniformly bright (intensity_mean index 0 high, low
    # texture/std since it's a flat-painted square).
    assert feature_vector.values[0] > 150  # intensity_mean
    assert feature_vector.values[1] < 10  # intensity_std (flat blob)


def test_classification_reports_not_trained_until_a_model_is_fitted(client: TestClient) -> None:
    survey = create_uploaded_survey(client, "Classification NotTrained Survey")

    from app.db.session import get_session_factory
    from app.models.survey import Survey
    from app.ml.model_registry import reset_registry_cache
    from app.services import classification_service, feature_service

    reset_registry_cache()
    db = get_session_factory()()
    try:
        survey_row = db.get(Survey, survey["id"])
        target = _make_target(db, survey_row)
        feature_vector = feature_service.extract_and_store_features(db, target, survey_row)
        classical_record, quantum_record = classification_service.classify_target(db, target, feature_vector)
    finally:
        db.close()

    assert classical_record.run_status.value == "NOT_TRAINED"
    assert classical_record.predicted_class is None
    assert classical_record.probabilities is None
    # Quantum: either genuinely NOT_TRAINED (qiskit available) or UNAVAILABLE
    # (qiskit not importable) -- never a fabricated prediction either way.
    assert quantum_record.run_status.value in ("NOT_TRAINED", "UNAVAILABLE")
    assert quantum_record.predicted_class is None


def test_classification_with_a_trained_fixture_model(client: TestClient, monkeypatch) -> None:
    """Trains a tiny deterministic classifier in-process (a legitimate test
    fixture per spec) and registers it, to prove the OK path genuinely
    updates the target and writes a real ClassificationRecord."""
    survey = create_uploaded_survey(client, "Classification Trained Survey")

    from app.db.session import get_session_factory
    from app.ml.classical_classifier import SklearnClassicalClassifier
    from app.models.survey import Survey
    from app.services import classification_service, feature_service

    trained = SklearnClassicalClassifier(model_version="test-fixture")
    X_train = np.array([[0, 0, 0, 0, 0, 0, 0, 0], [1, 1, 1, 1, 1, 1, 1, 1]] * 5)
    y_train = ["natural_seabed", "ghost_net"] * 5
    trained.fit(X_train, y_train)

    # monkeypatch auto-reverts at test teardown, so this can't leak into
    # other tests the way mutating the module attribute directly would.
    monkeypatch.setattr(classification_service, "get_classical_classifier", lambda: trained)

    db = get_session_factory()()
    try:
        survey_row = db.get(Survey, survey["id"])
        target = _make_target(db, survey_row)
        feature_vector = feature_service.extract_and_store_features(db, target, survey_row)
        classical_record, _ = classification_service.classify_target(db, target, feature_vector)
        db.refresh(target)
    finally:
        db.close()

    assert classical_record.run_status.value == "OK"
    assert classical_record.predicted_class in ("natural_seabed", "ghost_net")
    assert target.debris_subclass == classical_record.predicted_class
    assert target.uncertainty is not None


def test_uncertainty_high_for_close_probabilities() -> None:
    from app.services.uncertainty_service import compute_uncertainty

    result = compute_uncertainty({"ghost_net": 0.52, "natural_seabed": 0.43, "other_debris": 0.05})
    assert result.level.value in ("MEDIUM", "HIGH")
    assert result.score > 0.5


def test_uncertainty_low_for_confident_prediction() -> None:
    from app.services.uncertainty_service import compute_uncertainty

    result = compute_uncertainty({"natural_seabed": 0.98, "ghost_net": 0.02})
    assert result.level.value == "LOW"
    assert result.verification_required is False
