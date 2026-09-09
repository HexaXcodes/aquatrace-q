"""
Two-detector-slot integration tests (Phase 6).

`detection_service.run_detection()` now runs the general-purpose slot
(get_detection_model(), gated on the YOLO11s debris/gear checkpoint)
and the shipwreck-specialist slot (get_shipwreck_detection_model(),
gated on E004) independently and merges their results -- see
`app/ml/model_registry.py`'s module docstring for the reasoning. These
tests exercise that merge against the real registered detectors when
their (gitignored) checkpoints are present, and confirm the new debris/
gear/anthropogenic taxonomy gets the same classifier-protection
treatment E004's "shipwreck" already gets, without any new protection
code -- it falls out of `_detector_protected_class()` checking
vocabulary membership, not detector identity.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from tests.helpers import create_uploaded_survey

_E004_CHECKPOINT = Path(__file__).resolve().parents[1] / "models" / "E004_best.pt"
_YOLO_CHECKPOINT = Path(__file__).resolve().parents[1] / "models" / "yolo11s_marine_debris_best.pt"
_SAMPLE_IMAGE = (
    Path(__file__).resolve().parents[2]
    / "YOLO_TrainedModel"
    / "sample_sonar_images"
    / "marine-debris-aris3k-1123.png"  # real image with 2 detections, verified manually
)


def test_run_detection_merges_both_registered_models(client: TestClient, monkeypatch, tmp_path) -> None:
    if not _E004_CHECKPOINT.exists() or not _YOLO_CHECKPOINT.exists():
        pytest.skip("E004 and/or YOLO checkpoint not present (gitignored handoff artifacts)")
    if not _SAMPLE_IMAGE.exists():
        pytest.skip(f"Real sample image not present at {_SAMPLE_IMAGE}")

    from app.core.config import Settings, get_settings
    from app.ml.model_registry import reset_registry_cache

    model_dir = tmp_path / "models"
    model_dir.mkdir()
    shutil.copy(_E004_CHECKPOINT, model_dir / "E004_best.pt")
    shutil.copy(_YOLO_CHECKPOINT, model_dir / "yolo11s_marine_debris_best.pt")

    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("MODEL_DIRECTORY", str(model_dir))
    monkeypatch.setenv("ENABLE_SHIPWRECK_DETECTOR", "true")
    get_settings.cache_clear()
    reset_registry_cache()
    try:
        with open(_SAMPLE_IMAGE, "rb") as f:
            survey = create_uploaded_survey(client, "Multi-Model Detection Survey", image_bytes=f)

        from app.db.session import get_session_factory
        from app.models.survey import Survey
        from app.services import detection_service

        db = get_session_factory()()
        try:
            survey_row = db.get(Survey, survey["id"])
            detections = detection_service.run_detection(db, survey_row)
        finally:
            db.close()
    finally:
        get_settings.cache_clear()
        reset_registry_cache()

    # Both slots ran (neither raised); at minimum the general-purpose YOLO
    # slot found real debris on this real image (E004 may or may not fire
    # on a non-shipwreck image -- that's not asserted either way, since a
    # shipwreck-specific segmenter finding nothing on a debris photo isn't
    # a failure).
    model_names = {d.model_name for d in detections}
    assert "yolo11s-marine-debris-fls" in model_names
    assert model_names <= {"yolo11s-marine-debris-fls", "e004-unet-shipwreck-segmentation"}

    yolo_detections = [d for d in detections if d.model_name == "yolo11s-marine-debris-fls"]
    assert len(yolo_detections) >= 1
    for d in yolo_detections:
        # This image's real detections were verified (before any
        # integration code existed) to score 0.832/0.887 -- comfortably
        # above the manual-review band.
        assert d.requires_manual_review is False

    e004_detections = [d for d in detections if d.model_name == "e004-unet-shipwreck-segmentation"]
    for d in e004_detections:
        # E004 declares no manual-review policy -- None, never False.
        assert d.requires_manual_review is None


def _make_gear_hardware_target(db, survey_row):
    """A target whose originating detection carries the new YOLO
    taxonomy's subclass, the same shape YoloDebrisDetector produces --
    built directly against a hand-made Detection row so this test
    doesn't depend on the real checkpoint/ultralytics being present."""
    from app.models.detection import Detection
    from app.services import target_service

    detection = Detection(
        survey_id=survey_row.id,
        bbox=[10.0, 10.0, 50.0, 50.0],
        class_name="gear_hardware",
        confidence=0.87,
        requires_manual_review=False,
        model_name="yolo11s-marine-debris-fls",
        model_version="v1",
    )
    db.add(detection)
    db.commit()
    db.refresh(detection)

    targets = target_service.create_targets_from_detections(db, [detection])
    return targets[0]


def test_new_taxonomy_class_bootstraps_and_survives_target_creation(client: TestClient) -> None:
    survey = create_uploaded_survey(client, "Gear Hardware Bootstrap Survey")

    from app.db.session import get_session_factory
    from app.models.survey import Survey

    db = get_session_factory()()
    try:
        survey_row = db.get(Survey, survey["id"])
        target = _make_gear_hardware_target(db, survey_row)
    finally:
        db.close()

    assert target.debris_subclass == "gear_hardware"
    assert target.classification.value == "ANTHROPOGENIC"
    assert target.requires_manual_review is False


def test_new_taxonomy_class_is_protected_from_a_classifier_that_never_saw_it(
    client: TestClient, monkeypatch
) -> None:
    """Same protection E004's "shipwreck" already gets (see
    test_features_classification.py), proven here for the new YOLO
    taxonomy: the classical classifier's real trained vocabulary
    (background/tire/chain/propeller/can/bottle) does not include
    "gear_hardware" either, so _detector_protected_class() must keep it
    off Target rather than let a structurally-uninformed guess overwrite
    it -- no protection code was written specifically for this class;
    this proves the existing vocabulary-membership check covers it for
    free."""
    from app.ml.classical_classifier import SklearnClassicalClassifier
    from app.services import classification_service, feature_service

    trained = SklearnClassicalClassifier(model_version="test-fixture")
    X_train = np.array([[0, 0, 0, 0, 0, 0, 0, 0], [1, 1, 1, 1, 1, 1, 1, 1]] * 5)
    y_train = ["natural_seabed", "tire"] * 5
    trained.fit(X_train, y_train)
    assert "gear_hardware" not in trained.known_classes

    monkeypatch.setattr(classification_service, "get_classical_classifier", lambda: trained)

    survey = create_uploaded_survey(client, "Gear Hardware Protection Survey")

    from app.db.session import get_session_factory
    from app.models.survey import Survey

    db = get_session_factory()()
    try:
        survey_row = db.get(Survey, survey["id"])
        target = _make_gear_hardware_target(db, survey_row)

        feature_vector = feature_service.extract_and_store_features(db, target, survey_row)
        classical_record, _ = classification_service.classify_target(db, target, feature_vector)
        db.refresh(target)
    finally:
        db.close()

    assert classical_record.run_status.value == "OK"
    assert classical_record.note is not None and "gear_hardware" in classical_record.note
    assert target.debris_subclass == "gear_hardware"  # not overwritten
    assert target.requires_manual_review is False  # untouched by classification, as designed
