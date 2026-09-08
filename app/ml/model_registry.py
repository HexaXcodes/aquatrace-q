"""
Model registry (Phase 6/8/9).

Services never construct `FixtureThresholdDetector` /
`SklearnClassicalClassifier` / `QiskitQSVCClassifier` directly -- they
call `get_detection_model()` / `get_shipwreck_detection_model()` /
`get_classical_classifier()` / `get_quantum_classifier()`. This is the
one place that changes when a teammate's real model is ready:

    Shaun/Shashank: implement DetectionModel, then swap the instance
        returned by get_detection_model() (or extend the registry to
        pick a model by `settings.ML_MODEL_VERSION`).
    Shashank: call `SklearnClassicalClassifier.load(path)` with a real
        trained model file and register that instance instead of the
        untrained default.
    Aadvik: same, with `QiskitQSVCClassifier.load(path)`.

No other file needs to change.

**Two independent detection "slots", not one model replacing another**
(see docs/ml-integration.md for the full reasoning): `get_detection_model()`
is the general-purpose slot -- it answers "is there debris/gear/
anthropogenic material anywhere in this frame" and is gated on the
YOLO11s debris/gear detector's checkpoint, falling back to
`FixtureThresholdDetector` exactly as before if that checkpoint is
absent. `get_shipwreck_detection_model()` is a second, independent slot
for E004's narrow shipwreck-segmentation specialty -- it answers a
different, more specific question ("is this particular blob a
shipwreck") and returns `None` (not a fixture) when its checkpoint is
absent, since a generic classical-CV fallback standing in specifically
for "shipwreck detection" wouldn't mean anything. `detection_service.
run_detection()` calls both slots and merges whatever real detections
each one produces.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ml.base import DetectionModel
from app.ml.classical_classifier import ClassicalClassifier, SklearnClassicalClassifier
from app.ml.detection_model import FixtureThresholdDetector
from app.ml.quantum_classifier import QiskitQSVCClassifier, QiskitUnavailableError, QuantumClassifier

logger = get_logger(__name__)

_E004_CHECKPOINT_NAME = "E004_best.pt"
_YOLO_DEBRIS_CHECKPOINT_NAME = "yolo11s_marine_debris_best.pt"


@lru_cache
def get_detection_model() -> DetectionModel:
    """Returns the currently registered general-purpose detection model.

    Mirrors `get_classical_classifier()`'s gating: if a trained YOLO11s
    debris/gear checkpoint (`MODEL_DIRECTORY/yolo11s_marine_debris_best.pt`)
    is present, load and return the real `YoloDebrisDetector`. Otherwise
    (checkpoint missing, or ultralytics not importable in this
    environment) fall back to `FixtureThresholdDetector` -- a real (if
    crude) classical CV detector, never a fabricated prediction. Tests
    redirect `MODEL_DIRECTORY` to an empty tmp dir (see
    `tests/conftest.py`), so they exercise the fixture path unless they
    explicitly place a checkpoint there.

    This function used to gate on E004 directly (E004 was, for a while,
    the only real detector this project had). It now gates on the
    general-purpose YOLO11s detector instead -- see this module's
    docstring for why E004 moved to its own `get_shipwreck_detection_model()`
    slot rather than being replaced.
    """
    settings = get_settings()
    checkpoint_path = settings.MODEL_DIRECTORY / _YOLO_DEBRIS_CHECKPOINT_NAME
    if checkpoint_path.exists():
        try:
            from app.ml.yolo_debris_detector import UltralyticsUnavailableError, YoloDebrisDetector

            return YoloDebrisDetector(checkpoint_path=checkpoint_path)
        except UltralyticsUnavailableError as exc:
            logger.warning("yolo_debris_detector_unavailable", extra={"reason": str(exc)})

    return FixtureThresholdDetector()


@lru_cache
def get_shipwreck_detection_model() -> DetectionModel | None:
    """Returns the registered shipwreck-specialist detector (E004), or
    `None` if its checkpoint is absent or torch isn't importable --
    there's no meaningful fallback for a narrow specialist question like
    "is this a shipwreck," so unlike `get_detection_model()` this does
    NOT fall back to `FixtureThresholdDetector`. `detection_service.
    run_detection()` simply skips this slot when it returns `None`.
    """
    settings = get_settings()
    checkpoint_path = settings.MODEL_DIRECTORY / _E004_CHECKPOINT_NAME
    if checkpoint_path.exists():
        try:
            from app.ml.e004_detector import E004ShipwreckDetector, TorchUnavailableError

            return E004ShipwreckDetector(checkpoint_path=checkpoint_path)
        except TorchUnavailableError as exc:
            logger.warning("e004_detector_unavailable", extra={"reason": str(exc)})

    return None


@lru_cache
def get_classical_classifier() -> ClassicalClassifier:
    """
    Returns the classical classifier singleton.

    Attempts to load a trained model from `MODEL_DIRECTORY/classical_classifier.joblib`
    if one exists; otherwise returns an untrained instance whose
    `is_trained` is False. Callers MUST check `is_trained` and report
    `ModelRunStatus.NOT_TRAINED` rather than calling predict() on it.
    """
    settings = get_settings()
    classifier = SklearnClassicalClassifier(model_version=settings.ML_MODEL_VERSION or "dev")
    model_path = settings.MODEL_DIRECTORY / "classical_classifier.joblib"
    if model_path.exists():
        classifier.load(model_path)
    return classifier


@lru_cache
def get_quantum_classifier() -> QuantumClassifier | None:
    """
    Returns the quantum classifier singleton, or `None` if qiskit /
    qiskit-machine-learning are not importable in this environment
    (`ModelRunStatus.UNAVAILABLE`). If importable but not yet trained,
    returns an instance with `is_trained = False`
    (`ModelRunStatus.NOT_TRAINED`).
    """
    settings = get_settings()
    if not settings.QML_ENABLED:
        return None

    try:
        classifier = QiskitQSVCClassifier(n_qubits=settings.QML_FEATURE_DIMENSIONS)
    except QiskitUnavailableError:
        return None

    model_path = settings.MODEL_DIRECTORY / "quantum_classifier.pkl"
    if model_path.exists():
        classifier.load(model_path)
    return classifier


def reset_registry_cache() -> None:
    """Test-only: clear cached singletons so tests can register fresh
    (e.g. freshly trained) model instances without process restart."""
    get_detection_model.cache_clear()
    get_shipwreck_detection_model.cache_clear()
    get_classical_classifier.cache_clear()
    get_quantum_classifier.cache_clear()
