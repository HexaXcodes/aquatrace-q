from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from tests.helpers import create_uploaded_survey


def _make_target(db, survey_row):
    from app.services import detection_service, target_service

    detections = detection_service.run_detection(db, survey_row)
    targets = target_service.create_targets_from_detections(db, detections)
    return targets[0]


def _make_shipwreck_target(db, survey_row):
    """A target whose originating detection carries a detector-specific
    subclass (`class_name="shipwreck"`), the same shape E004ShipwreckDetector
    produces -- built directly against a hand-made Detection row rather than
    running the real E004 checkpoint, so this test doesn't depend on torch or
    the (gitignored) model file being present."""
    from app.models.detection import Detection
    from app.services import target_service

    detection = Detection(
        survey_id=survey_row.id,
        bbox=[10.0, 10.0, 50.0, 50.0],
        class_name="shipwreck",
        confidence=0.987,
        model_name="e004-unet-shipwreck-segmentation",
        model_version="E004",
    )
    db.add(detection)
    db.commit()
    db.refresh(detection)

    targets = target_service.create_targets_from_detections(db, [detection])
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


def test_classifier_cannot_overwrite_a_class_it_was_never_trained_on(client: TestClient, monkeypatch) -> None:
    """Regression test for the classification-overwrite bug: a detector
    (E004ShipwreckDetector in production; a hand-built shipwreck Detection
    here, see _make_shipwreck_target) flags a target as "shipwreck", but the
    classical classifier was only ever trained on natural_seabed/ghost_net --
    it has never seen a shipwreck example. Its prediction must NOT silently
    overwrite the target's classification/debris_subclass/confidence, and
    must still be fully visible on the ClassificationRecord."""
    survey = create_uploaded_survey(client, "Classification Protected Survey")

    from app.db.session import get_session_factory
    from app.ml.classical_classifier import SklearnClassicalClassifier
    from app.models.survey import Survey
    from app.services import classification_service, feature_service

    trained = SklearnClassicalClassifier(model_version="test-fixture")
    X_train = np.array([[0, 0, 0, 0, 0, 0, 0, 0], [1, 1, 1, 1, 1, 1, 1, 1]] * 5)
    y_train = ["natural_seabed", "ghost_net"] * 5
    trained.fit(X_train, y_train)
    assert "shipwreck" not in trained.known_classes

    monkeypatch.setattr(classification_service, "get_classical_classifier", lambda: trained)

    db = get_session_factory()()
    try:
        survey_row = db.get(Survey, survey["id"])
        target = _make_shipwreck_target(db, survey_row)
        assert target.debris_subclass == "shipwreck"  # bootstrap value survived target creation

        feature_vector = feature_service.extract_and_store_features(db, target, survey_row)
        classical_record, _ = classification_service.classify_target(db, target, feature_vector)
        db.refresh(target)
    finally:
        db.close()

    # The classifier still ran and produced a real (if structurally
    # uninformed) prediction -- it's just not authoritative for this target.
    assert classical_record.run_status.value == "OK"
    assert classical_record.predicted_class in ("natural_seabed", "ghost_net")
    assert classical_record.probabilities is not None
    assert classical_record.note is not None and "shipwreck" in classical_record.note

    # The detector's own class signal must survive, not be overwritten.
    assert target.debris_subclass == "shipwreck"
    assert target.classification.value == "ANTHROPOGENIC"
    assert target.confidence == 0.987  # E004's own detection confidence, untouched
    assert target.uncertainty is None  # never computed from a prediction that wasn't applied


def test_classifier_can_overwrite_once_it_knows_the_detector_class(client: TestClient, monkeypatch) -> None:
    """Mirror image of the protection test: once the classical classifier's
    trained vocabulary *does* include the detector's class (e.g. after
    Shashank supplies real shipwreck-labelled training data), the protection
    must stop applying automatically -- no further code change required."""
    survey = create_uploaded_survey(client, "Classification Overlap Survey")

    from app.db.session import get_session_factory
    from app.ml.classical_classifier import SklearnClassicalClassifier
    from app.models.survey import Survey
    from app.services import classification_service, feature_service

    trained = SklearnClassicalClassifier(model_version="test-fixture-with-shipwreck")
    X_train = np.array([[0, 0, 0, 0, 0, 0, 0, 0], [1, 1, 1, 1, 1, 1, 1, 1]] * 5)
    y_train = ["natural_seabed", "shipwreck"] * 5
    trained.fit(X_train, y_train)
    assert "shipwreck" in trained.known_classes

    monkeypatch.setattr(classification_service, "get_classical_classifier", lambda: trained)

    db = get_session_factory()()
    try:
        survey_row = db.get(Survey, survey["id"])
        target = _make_shipwreck_target(db, survey_row)

        feature_vector = feature_service.extract_and_store_features(db, target, survey_row)
        classical_record, _ = classification_service.classify_target(db, target, feature_vector)
        db.refresh(target)
    finally:
        db.close()

    assert classical_record.run_status.value == "OK"
    assert classical_record.note is None  # nothing to explain -- applied normally
    assert target.debris_subclass == classical_record.predicted_class
    assert target.uncertainty is not None  # computed normally, since the result was applied


def test_protection_holds_against_the_real_registered_classifier(client: TestClient, monkeypatch, tmp_path) -> None:
    """The two tests above use a classifier hand-built in-process via
    SklearnClassicalClassifier -- they prove _detector_protected_class()'s
    *logic* is right, but not that it engages through the real
    model_registry.get_classical_classifier() path with an actually-loaded
    `models/classical_classifier.joblib` on disk, which is what production
    (and any real dev-server run) actually calls. That gap matters: a bug
    report once claimed this protection wasn't engaging in a live server --
    investigation found no code defect (this exact scenario, run fresh,
    protects correctly every time -- see docs/ml-integration.md for the
    live evidence and the stale-process theory that actually explained it),
    but "prove it against the real registry, not just a hand-built
    classifier" was a legitimate gap in coverage regardless of that
    particular report's root cause, so closing it here."""
    real_model_path = Path(__file__).resolve().parents[1] / "models" / "classical_classifier.joblib"
    if not real_model_path.exists():
        pytest.skip(f"Real classical classifier not present at {real_model_path} (gitignored trained artifact)")

    from app.core.config import Settings, get_settings
    from app.ml.model_registry import get_classical_classifier, reset_registry_cache

    model_dir = tmp_path / "models"
    model_dir.mkdir()
    shutil.copy(real_model_path, model_dir / "classical_classifier.joblib")

    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("MODEL_DIRECTORY", str(model_dir))
    get_settings.cache_clear()
    reset_registry_cache()
    try:
        classifier = get_classical_classifier()
        assert classifier.is_trained
        # This is the exact real-world precondition for the protection to
        # matter: the actually-trained classifier's vocabulary does not
        # include "shipwreck" at all (see docs/ml-integration.md's FLS
        # benchmark note). If this assertion ever fails, it means real
        # shipwreck-labelled training data has landed -- see the mirror
        # test above for what should happen then.
        assert "shipwreck" not in classifier.known_classes

        survey = create_uploaded_survey(client, "Real Registry Protection Survey")
        from app.db.session import get_session_factory
        from app.models.survey import Survey
        from app.services import classification_service, feature_service

        db = get_session_factory()()
        try:
            survey_row = db.get(Survey, survey["id"])
            target = _make_shipwreck_target(db, survey_row)
            feature_vector = feature_service.extract_and_store_features(db, target, survey_row)
            classical_record, _ = classification_service.classify_target(db, target, feature_vector)
            db.refresh(target)
        finally:
            db.close()

        assert classical_record.run_status.value == "OK"
        assert classical_record.note is not None and "shipwreck" in classical_record.note
        assert target.debris_subclass == "shipwreck"
        assert target.classification.value == "ANTHROPOGENIC"
        assert target.confidence == 0.987
    finally:
        get_settings.cache_clear()
        reset_registry_cache()


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
