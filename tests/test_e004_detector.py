"""
E004 shipwreck segmentation detector tests (Phase 6).

These exercise the real trained `E004_best.pt` checkpoint end-to-end --
not a mock. They're skipped (not failed) if the checkpoint isn't present
on disk (`models/*` is gitignored, same as classical_classifier.joblib /
quantum_classifier.pkl) or torch isn't importable: a missing optional
artifact/dependency is an environment fact, not a code defect, exactly
the convention `test_quantum.py` already uses for qiskit.

`FixtureThresholdDetector` keeps its own dedicated coverage in
`test_detections_targets.py` unchanged -- these are new tests for the
new adapter, not a replacement for the existing ones.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from tests.helpers import shipwreck_like_array

_CHECKPOINT_PATH = Path(__file__).resolve().parents[1] / "models" / "E004_best.pt"


def _load_detector():
    if not _CHECKPOINT_PATH.exists():
        pytest.skip(f"E004 checkpoint not present at {_CHECKPOINT_PATH} (gitignored handoff artifact)")

    from app.ml.e004_detector import E004ShipwreckDetector, TorchUnavailableError

    try:
        return E004ShipwreckDetector(checkpoint_path=_CHECKPOINT_PATH)
    except TorchUnavailableError:
        pytest.skip("torch not importable in this environment")


@pytest.fixture(scope="module")
def detector():
    return _load_detector()


def _assert_valid_detections(detections, width: int, height: int) -> None:
    assert isinstance(detections, list)
    for detection in detections:
        assert detection.class_name == "shipwreck"
        assert 0.0 <= detection.confidence <= 1.0
        assert detection.bbox is not None
        x1, y1, x2, y2 = detection.bbox
        assert 0.0 <= x1 < x2 <= width
        assert 0.0 <= y1 < y2 <= height
        assert detection.mask_path is not None
        mask_file = Path(detection.mask_path)
        assert mask_file.exists()
        with Image.open(mask_file) as mask_img:
            assert mask_img.mode == "L"
            saved_mask = np.asarray(mask_img)
        # Not empty, not solid -- a real component crop, not a placeholder.
        assert saved_mask.max() > 0


def test_loads_real_checkpoint(detector) -> None:
    assert detector.model_name == "e004-unet-shipwreck-segmentation"
    assert detector.model_version == "E004"


def test_predict_on_pure_noise_finds_nothing(tmp_path, detector) -> None:
    """No painted shape -> the model should not hallucinate a shipwreck
    out of plain mottled seabed texture (confirmed manually: max sigmoid
    probability ~0.0008 on this exact kind of background)."""
    rng = np.random.default_rng(3)
    background = rng.normal(loc=70, scale=8, size=(220, 300)).clip(0, 255).astype(np.uint8)
    image_path = tmp_path / "noise.png"
    Image.fromarray(background, mode="L").save(image_path)

    detections = detector.predict(image_path)
    assert detections == []


def test_predict_on_small_image_finds_the_painted_shape(tmp_path, settings_output_dir, detector) -> None:
    """Below one tile (300x220): exercises the zero-pad-to-1024 path.
    A real shipwreck-like blob painted into the image should be picked
    up, with a bbox that (loosely) surrounds where it was actually
    painted -- not an arbitrary/empty result."""
    width, height = 300, 220
    cx, cy = 150, 110
    array = shipwreck_like_array(width, height, cx=cx, cy=cy, length=90, half_width=25)
    image_path = tmp_path / "small_sonar.png"
    Image.fromarray(array, mode="L").save(image_path)

    detections = detector.predict(image_path)
    _assert_valid_detections(detections, width, height)
    assert len(detections) >= 1

    # At least one detected bbox should overlap the painted hull's center.
    assert any(d.bbox[0] <= cx <= d.bbox[2] and d.bbox[1] <= cy <= d.bbox[3] for d in detections)


def test_predict_on_multi_tile_image_stitches_global_coordinates(tmp_path, settings_output_dir, detector) -> None:
    """Larger than one tile in both dimensions (2200x1500 -> a 3x2 tile
    grid at 1024 each): the painted shape sits inside the *second* tile
    column/row, so a correct stitch requires the per-tile bbox to be
    offset by (x0, y0), not reported in tile-local coordinates."""
    width, height = 2200, 1500
    # Place the shape inside tile (col=1, row=1): x in [1024, 2048), y in [1024, 1500).
    cx, cy = 1024 + 400, 1024 + 200
    array = shipwreck_like_array(width, height, cx=cx, cy=cy, length=100, half_width=30)

    image_path = tmp_path / "large_sonar.png"
    Image.fromarray(array, mode="L").save(image_path)

    detections = detector.predict(image_path)
    _assert_valid_detections(detections, width, height)
    assert len(detections) >= 1
    assert any(d.bbox[0] <= cx <= d.bbox[2] and d.bbox[1] <= cy <= d.bbox[3] for d in detections)


def test_registered_as_shipwreck_specialist_when_checkpoint_present(tmp_path, monkeypatch) -> None:
    """E004 moved from the general get_detection_model() slot to its own
    get_shipwreck_detection_model() slot when the YOLO11s debris/gear
    detector was integrated as the new general-purpose default -- see
    app/ml/model_registry.py's module docstring."""
    if not _CHECKPOINT_PATH.exists():
        pytest.skip(f"E004 checkpoint not present at {_CHECKPOINT_PATH} (gitignored handoff artifact)")

    import shutil

    from app.core.config import Settings, get_settings
    from app.ml.model_registry import get_shipwreck_detection_model, reset_registry_cache

    model_dir = tmp_path / "models"
    model_dir.mkdir()
    shutil.copy(_CHECKPOINT_PATH, model_dir / "E004_best.pt")

    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("MODEL_DIRECTORY", str(model_dir))
    monkeypatch.setenv("ENABLE_SHIPWRECK_DETECTOR", "true")
    get_settings.cache_clear()
    reset_registry_cache()
    try:
        model = get_shipwreck_detection_model()
        assert model is not None
        assert model.model_name == "e004-unet-shipwreck-segmentation"
    finally:
        get_settings.cache_clear()
        reset_registry_cache()


def test_shipwreck_slot_is_none_when_checkpoint_absent() -> None:
    """`tests/conftest.py`'s autouse fixture already redirects
    MODEL_DIRECTORY to an empty tmp dir for every test -- this just makes
    that fallback behavior an explicit, named assertion. Unlike the
    general get_detection_model() slot, the shipwreck specialist slot has
    no fixture fallback -- it's just None."""
    from app.ml.model_registry import get_shipwreck_detection_model

    assert get_shipwreck_detection_model() is None


def test_general_slot_falls_back_to_fixture_when_yolo_checkpoint_absent() -> None:
    """get_detection_model() (the general-purpose slot) now gates on the
    YOLO11s debris/gear checkpoint, not E004 -- still falls back to
    FixtureThresholdDetector when that's absent, same as before."""
    from app.ml.detection_model import FixtureThresholdDetector
    from app.ml.model_registry import get_detection_model

    assert isinstance(get_detection_model(), FixtureThresholdDetector)


@pytest.fixture()
def settings_output_dir(tmp_path, monkeypatch):
    """`E004ShipwreckDetector._save_mask_crop` writes under
    `settings.OUTPUT_DIRECTORY` -- redirect it to a tmp dir so these
    tests don't leave files behind in the real `outputs/` directory."""
    from app.core.config import Settings, get_settings

    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv("OUTPUT_DIRECTORY", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
