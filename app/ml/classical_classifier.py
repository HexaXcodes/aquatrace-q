"""
`ClassicalClassifier` (Phase 8).

`SklearnClassicalClassifier` is a real, working classifier (logistic
regression by default, swappable for SVM/Random Forest via the
`estimator` constructor argument) -- not a mock. It genuinely calls
`fit`/`predict`/`predict_proba` on scikit-learn and persists itself
with `joblib`.

What it is NOT is *trained on real labelled sonar data yet* -- Shashank
owns that dataset. Until a trained model is loaded via `load()`,
`model_registry.get_classical_classifier()` returns an instance whose
`is_trained` is False, and callers must treat that as
`ModelRunStatus.NOT_TRAINED`, never silently predicting with an
untrained estimator.
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)


@dataclass(slots=True)
class ClassificationResult:
    predicted_class: str
    probabilities: dict[str, float]
    confidence: float
    model_name: str
    model_version: str
    feature_version: str
    inference_time_ms: float = 0.0


@dataclass(slots=True)
class EvaluationMetrics:
    accuracy: float
    precision: float
    recall: float
    f1: float
    confusion_matrix: list[list[int]]
    sample_count: int
    inference_time_ms: float = 0.0
    extra: dict = field(default_factory=dict)


class ClassicalClassifier(abc.ABC):
    model_name: str = "unregistered"
    model_version: str = "0.0.0"
    feature_version: str = "unknown"
    is_trained: bool = False

    @abc.abstractmethod
    def fit(self, X: np.ndarray, y: list[str]) -> None: ...

    @abc.abstractmethod
    def predict(self, X: np.ndarray) -> list[str]: ...

    @abc.abstractmethod
    def predict_proba(self, X: np.ndarray) -> np.ndarray: ...

    @abc.abstractmethod
    def evaluate(self, X: np.ndarray, y: list[str]) -> EvaluationMetrics: ...

    @abc.abstractmethod
    def save(self, path: Path) -> None: ...

    @abc.abstractmethod
    def load(self, path: Path) -> None: ...


class SklearnClassicalClassifier(ClassicalClassifier):
    model_name = "sklearn-classical-classifier"

    def __init__(self, estimator: object | None = None, model_version: str = "dev") -> None:
        self._estimator = estimator or LogisticRegression(max_iter=1000)
        self.model_version = model_version
        self._classes: list[str] = []
        self.is_trained = False

    def fit(self, X: np.ndarray, y: list[str]) -> None:
        self._estimator.fit(X, y)
        self._classes = list(self._estimator.classes_)
        self.is_trained = True

    def predict(self, X: np.ndarray) -> list[str]:
        self._require_trained()
        return list(self._estimator.predict(X))

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        self._require_trained()
        return self._estimator.predict_proba(X)

    def predict_one(self, x: np.ndarray, feature_version: str) -> ClassificationResult:
        self._require_trained()
        start = time.perf_counter()
        proba = self._estimator.predict_proba(x.reshape(1, -1))[0]
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        probabilities = {cls: float(p) for cls, p in zip(self._classes, proba, strict=True)}
        predicted_class = max(probabilities, key=probabilities.get)
        return ClassificationResult(
            predicted_class=predicted_class,
            probabilities=probabilities,
            confidence=probabilities[predicted_class],
            model_name=self.model_name,
            model_version=self.model_version,
            feature_version=feature_version,
            inference_time_ms=elapsed_ms,
        )

    def evaluate(self, X: np.ndarray, y: list[str]) -> EvaluationMetrics:
        self._require_trained()
        start = time.perf_counter()
        predictions = self.predict(X)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        labels = sorted(set(y) | set(predictions))
        return EvaluationMetrics(
            accuracy=float(accuracy_score(y, predictions)),
            precision=float(precision_score(y, predictions, average="macro", zero_division=0)),
            recall=float(recall_score(y, predictions, average="macro", zero_division=0)),
            f1=float(f1_score(y, predictions, average="macro", zero_division=0)),
            confusion_matrix=confusion_matrix(y, predictions, labels=labels).tolist(),
            sample_count=len(y),
            inference_time_ms=elapsed_ms,
            extra={"labels": labels},
        )

    def save(self, path: Path) -> None:
        self._require_trained()
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "estimator": self._estimator,
                "classes": self._classes,
                "model_version": self.model_version,
            },
            path,
        )

    def load(self, path: Path) -> None:
        payload = joblib.load(path)
        self._estimator = payload["estimator"]
        self._classes = payload["classes"]
        self.model_version = payload["model_version"]
        self.is_trained = True

    def _require_trained(self) -> None:
        if not self.is_trained:
            raise RuntimeError(
                "SklearnClassicalClassifier.fit()/load() must be called before "
                "predict/predict_proba/evaluate. Callers should catch this and "
                "report ModelRunStatus.NOT_TRAINED rather than crashing the pipeline."
            )
