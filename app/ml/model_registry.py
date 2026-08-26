"""
Model registry (Phase 6/8/9).

Services never construct `FixtureThresholdDetector` /
`SklearnClassicalClassifier` / `QiskitQSVCClassifier` directly -- they
call `get_detection_model()` / `get_classical_classifier()` /
`get_quantum_classifier()`. This is the one place that changes when a
teammate's real model is ready:

    Shaun/Shashank: implement DetectionModel, then swap the instance
        returned by get_detection_model() (or extend the registry to
        pick a model by `settings.ML_MODEL_VERSION`).
    Shashank: call `SklearnClassicalClassifier.load(path)` with a real
        trained model file and register that instance instead of the
        untrained default.
    Aadvik: same, with `QiskitQSVCClassifier.load(path)`.

No other file needs to change.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.ml.base import DetectionModel
from app.ml.classical_classifier import ClassicalClassifier, SklearnClassicalClassifier
from app.ml.detection_model import FixtureThresholdDetector
from app.ml.quantum_classifier import QiskitQSVCClassifier, QiskitUnavailableError, QuantumClassifier


@lru_cache
def get_detection_model() -> DetectionModel:
    """Returns the currently registered detection model.

    Today: `FixtureThresholdDetector`, a real (if crude) classical CV
    detector -- see its docstring for why this is an honest stand-in
    rather than fabricated output. Swap this function's body to return
    a real trained model once Shaun/Shashank register one.
    """
    return FixtureThresholdDetector()


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
    get_classical_classifier.cache_clear()
    get_quantum_classifier.cache_clear()
