"""
YOLO11s marine debris/gear detector tests (Phase 6).

Real-checkpoint tests exercise `models/yolo11s_marine_debris_best.pt`
(and the real ARIS sample images shipped alongside it in
`YOLO_TrainedModel/sample_sonar_images/`) end-to-end -- not a mock.
Skipped (not failed) if the checkpoint isn't present on disk (gitignored
handoff artifact, same convention as E004/classical/quantum) or
ultralytics isn't importable: a missing optional artifact/dependency is
an environment fact, not a code defect.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_CHECKPOINT_PATH = Path(__file__).resolve().parents[1] / "models" / "yolo11s_marine_debris_best.pt"
_SAMPLE_IMAGES_DIR = (
    Path(__file__).resolve().parents[2] / "YOLO_TrainedModel" / "sample_sonar_images"
)
_CONTRACT_CLASSES = {"marine_debris", "gear_hardware", "other_anthropogenic"}


def _load_detector():
    if not _CHECKPOINT_PATH.exists():
        pytest.skip(f"YOLO checkpoint not present at {_CHECKPOINT_PATH} (gitignored handoff artifact)")

    from app.ml.yolo_debris_detector import UltralyticsUnavailableError, YoloDebrisDetector

    try:
        return YoloDebrisDetector(checkpoint_path=_CHECKPOINT_PATH)
    except UltralyticsUnavailableError:
        pytest.skip("ultralytics not importable in this environment")


@pytest.fixture(scope="module")
def detector():
    return _load_detector()


def test_loads_real_checkpoint(detector) -> None:
    assert detector.model_name == "yolo11s-marine-debris-fls"
    assert detector.model_version == "v1"


def test_predict_on_real_sample_images_finds_real_objects(detector) -> None:
    """Runs the real checkpoint against all 5 real ARIS 3000 sample
    images from the handoff -- confirms genuine, varying detections
    (not a static/hallucinated output), each with a contract-declared
    class name and a plausible bbox inside the image bounds. Matches
    the manual verification run before any integration code was
    written: 7 real detections across the 5 samples, confidences
    0.588-0.887, classes exactly {marine_debris, gear_hardware,
    other_anthropogenic}."""
    if not _SAMPLE_IMAGES_DIR.exists():
        pytest.skip(f"Sample images not present at {_SAMPLE_IMAGES_DIR}")

    sample_images = sorted(_SAMPLE_IMAGES_DIR.glob("*.png"))
    assert len(sample_images) == 5

    from PIL import Image

    total_detections = 0
    seen_classes: set[str] = set()
    for image_path in sample_images:
        with Image.open(image_path) as img:
            width, height = img.size

        detections = detector.predict(image_path)
        total_detections += len(detections)
        for d in detections:
            assert d.class_name in _CONTRACT_CLASSES
            seen_classes.add(d.class_name)
            assert 0.0 <= d.confidence <= 1.0
            assert d.bbox is not None
            x1, y1, x2, y2 = d.bbox
            assert 0.0 <= x1 < x2 <= width
            assert 0.0 <= y1 < y2 <= height
            assert d.mask_path is None  # bbox detector, no segmentation
            # Real sample images all scored well above the manual-review
            # band (0.588-0.887 measured) -- not flagged.
            assert d.requires_manual_review is False

    assert total_detections >= 5  # real signal, not an empty/degenerate result
    assert seen_classes  # at least one real class actually appeared


def test_predict_on_pure_noise_finds_nothing_or_low_confidence(tmp_path, detector) -> None:
    """No real sonar structure -> should not hallucinate confident debris
    out of plain noise. Doesn't assert zero detections outright (a CNN
    can still fire on noise at low confidence) -- asserts nothing is
    reported above the model's own declared floor with high confidence,
    i.e. no confident false positive."""
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(5)
    background = rng.normal(loc=70, scale=8, size=(300, 400)).clip(0, 255).astype(np.uint8)
    image_path = tmp_path / "noise.png"
    Image.fromarray(background, mode="L").save(image_path)

    detections = detector.predict(image_path)
    assert all(d.confidence < 0.5 for d in detections)  # nothing confidently misclassified as debris


def test_manual_review_boundary_is_a_pure_function() -> None:
    """Unit-tests the [0.25, 0.5) boundary logic directly (model_contract.json's
    declared manual_review_range/default_confidence_threshold), without
    needing a real ultralytics Results object."""
    from app.ml.yolo_debris_detector import _requires_manual_review

    default_threshold, review_range = 0.5, (0.25, 0.5)
    assert _requires_manual_review(0.25, default_threshold, review_range) is True  # inclusive lower bound
    assert _requires_manual_review(0.3, default_threshold, review_range) is True
    assert _requires_manual_review(0.49999, default_threshold, review_range) is True
    assert _requires_manual_review(0.5, default_threshold, review_range) is False  # exclusive upper bound
    assert _requires_manual_review(0.9, default_threshold, review_range) is False
    assert _requires_manual_review(0.1, default_threshold, review_range) is False  # below the floor entirely


def test_registered_as_general_detection_model_when_checkpoint_present(tmp_path, monkeypatch) -> None:
    if not _CHECKPOINT_PATH.exists():
        pytest.skip(f"YOLO checkpoint not present at {_CHECKPOINT_PATH} (gitignored handoff artifact)")

    import shutil

    from app.core.config import Settings, get_settings
    from app.ml.model_registry import get_detection_model, reset_registry_cache

    model_dir = tmp_path / "models"
    model_dir.mkdir()
    shutil.copy(_CHECKPOINT_PATH, model_dir / "yolo11s_marine_debris_best.pt")

    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("MODEL_DIRECTORY", str(model_dir))
    get_settings.cache_clear()
    reset_registry_cache()
    try:
        model = get_detection_model()
        assert model.model_name == "yolo11s-marine-debris-fls"
    finally:
        get_settings.cache_clear()
        reset_registry_cache()
