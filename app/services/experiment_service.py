"""
Experiment service (Phase 9/20).

Runs a classical-vs-quantum classification comparison on a supplied
labelled dataset and stores the measured metrics for both sides. If a
side has no trained/available model, its `*_status` is set to
`NOT_TRAINED`/`UNAVAILABLE` and its metrics are left `None` -- never
backfilled with invented numbers, and no comparison implies a "winner"
beyond what the stored numbers show.
"""

from __future__ import annotations

import numpy as np
from sklearn.model_selection import train_test_split
from sqlalchemy.orm import Session

from app.core.exceptions import ExperimentNotFoundError
from app.ml.classical_classifier import SklearnClassicalClassifier
from app.ml.quantum_classifier import QiskitQSVCClassifier, QiskitUnavailableError
from app.models.experiment import Experiment


def run_classification_experiment(
    db: Session,
    X: np.ndarray,
    y: list[str],
    dataset_version: str,
    feature_version: str,
    test_size: float = 0.3,
    random_state: int = 0,
) -> Experiment:
    if len(set(y)) < 2:
        raise ValueError("Experiment dataset must contain at least two classes.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    classical_status, classical_metrics = _run_classical(X_train, y_train, X_test, y_test)
    quantum_status, quantum_metrics = _run_quantum(X_train, y_train, X_test, y_test)

    experiment = Experiment(
        dataset_version=dataset_version,
        feature_version=feature_version,
        sample_count=len(y),
        classical_status=classical_status,
        classical_metrics=classical_metrics,
        quantum_status=quantum_status,
        quantum_metrics=quantum_metrics,
        notes=(
            "Metrics are measured on this run's train/test split only; no "
            "quantum-advantage claim is made or implied by this comparison."
        ),
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


def _run_classical(X_train, y_train, X_test, y_test) -> tuple[str, dict | None]:
    classifier = SklearnClassicalClassifier(model_version="experiment")
    classifier.fit(X_train, y_train)
    metrics = classifier.evaluate(X_test, y_test)
    return "OK", {
        "accuracy": metrics.accuracy,
        "precision": metrics.precision,
        "recall": metrics.recall,
        "f1": metrics.f1,
        "confusion_matrix": metrics.confusion_matrix,
        "sample_count": metrics.sample_count,
        "inference_time_ms": metrics.inference_time_ms,
        "labels": metrics.extra.get("labels"),
    }


def _run_quantum(X_train, y_train, X_test, y_test) -> tuple[str, dict | None]:
    try:
        n_qubits = min(4, X_train.shape[1])
        classifier = QiskitQSVCClassifier(n_qubits=n_qubits, model_version="experiment")
    except QiskitUnavailableError:
        return "UNAVAILABLE", None

    try:
        classifier.fit(X_train, y_train)
        metrics = classifier.evaluate(X_test, y_test)
    except QiskitUnavailableError:
        return "UNAVAILABLE", None

    return "OK", {
        "accuracy": metrics.accuracy,
        "precision": metrics.precision,
        "recall": metrics.recall,
        "f1": metrics.f1,
        "confusion_matrix": metrics.confusion_matrix,
        "sample_count": metrics.sample_count,
        "inference_time_ms": metrics.inference_time_ms,
        "labels": metrics.extra.get("labels"),
        "n_qubits": metrics.extra.get("n_qubits"),
    }


def get_experiment(db: Session, experiment_id: str) -> Experiment:
    experiment = db.get(Experiment, experiment_id)
    if experiment is None:
        raise ExperimentNotFoundError(
            f"Experiment '{experiment_id}' does not exist.", experiment_id=experiment_id
        )
    return experiment
