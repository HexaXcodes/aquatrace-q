"""
Dedicated QML pipeline test (Phase 9).

Proves the real Qiskit pipeline (ZZFeatureMap -> FidelityQuantumKernel
-> QSVC) executes end-to-end in this environment, independent of the
rest of the application. If qiskit/qiskit-machine-learning aren't
importable in a given environment, this test is skipped rather than
failed -- that's a deployment-environment fact, not a code defect.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.ml.quantum_classifier import QiskitQSVCClassifier, QiskitUnavailableError


def _toy_dataset(n_per_class: int = 6, n_features: int = 4, seed: int = 0):
    rng = np.random.default_rng(seed)
    class_a = rng.normal(loc=0.2, scale=0.05, size=(n_per_class, n_features))
    class_b = rng.normal(loc=0.8, scale=0.05, size=(n_per_class, n_features))
    X = np.vstack([class_a, class_b])
    y = ["natural_seabed"] * n_per_class + ["ghost_net"] * n_per_class
    return X, y


def test_quantum_classifier_reports_not_trained_before_fit() -> None:
    try:
        classifier = QiskitQSVCClassifier(n_qubits=4)
    except QiskitUnavailableError:
        pytest.skip("qiskit/qiskit-machine-learning not importable in this environment")

    assert classifier.is_trained is False
    with pytest.raises(RuntimeError):
        classifier.predict(np.zeros((1, 4)))


def test_quantum_pipeline_fits_and_predicts() -> None:
    try:
        classifier = QiskitQSVCClassifier(n_qubits=4, reps=1)
    except QiskitUnavailableError:
        pytest.skip("qiskit/qiskit-machine-learning not importable in this environment")

    X, y = _toy_dataset()
    classifier.fit(X, y)
    assert classifier.is_trained is True

    predictions = classifier.predict(X)
    assert len(predictions) == len(y)

    proba = classifier.predict_proba(X)
    assert proba.shape == (len(y), 2)
    assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-6)

    metrics = classifier.evaluate(X, y)
    assert 0.0 <= metrics.accuracy <= 1.0
    assert metrics.sample_count == len(y)


def test_quantum_classifier_save_and_load(tmp_path) -> None:
    try:
        classifier = QiskitQSVCClassifier(n_qubits=4, reps=1, model_version="v-test")
    except QiskitUnavailableError:
        pytest.skip("qiskit/qiskit-machine-learning not importable in this environment")

    X, y = _toy_dataset()
    classifier.fit(X, y)
    original_predictions = classifier.predict(X)

    save_path = tmp_path / "quantum_classifier.pkl"
    classifier.save(save_path)

    reloaded = QiskitQSVCClassifier(n_qubits=4, reps=1)
    assert reloaded.is_trained is False
    reloaded.load(save_path)
    assert reloaded.is_trained is True
    assert reloaded.model_version == "v-test"

    reloaded_predictions = reloaded.predict(X)
    assert list(reloaded_predictions) == list(original_predictions)


def test_quantum_classifier_rejects_out_of_range_qubits() -> None:
    with pytest.raises(ValueError):
        QiskitQSVCClassifier(n_qubits=1)
    with pytest.raises(ValueError):
        QiskitQSVCClassifier(n_qubits=9)
