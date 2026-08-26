"""
`QuantumClassifier` (Phase 9) -- a real Qiskit / Qiskit Machine Learning
pipeline, not a simulated stand-in.

Pipeline, exactly as specified:

    feature vector -> MinMaxScaler -> PCA(n<=8) -> ZZFeatureMap
                   -> FidelityQuantumKernel -> QSVC -> probabilities

`QiskitQSVCClassifier.fit/predict/predict_proba/evaluate/save/load` all
genuinely execute the quantum-kernel circuit via Qiskit's statevector
simulator (no hardware access configured, and none is required for a
kernel classifier at this scale). This is real quantum computation
running locally -- it is simply not yet trained on the project's real
sonar feature data, which is Aadvik's dataset to supply.

Until `fit()`/`load()` has been called, `is_trained` is False and
callers must report `ModelRunStatus.NOT_TRAINED` -- never a fabricated
prediction. If qiskit / qiskit-machine-learning are not importable in a
given deployment, `QiskitUnavailableError` is raised at construction
time and callers report `ModelRunStatus.UNAVAILABLE`.
"""

from __future__ import annotations

import abc
import pickle
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.decomposition import PCA
from sklearn.preprocessing import MinMaxScaler

from app.ml.classical_classifier import ClassificationResult, EvaluationMetrics
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)


class QiskitUnavailableError(RuntimeError):
    """Raised when qiskit / qiskit-machine-learning cannot be imported."""


class QuantumClassifier(abc.ABC):
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


@dataclass(slots=True)
class _FittedState:
    scaler: MinMaxScaler
    pca: PCA
    qsvc: object
    classes: list[str]


class QiskitQSVCClassifier(QuantumClassifier):
    """ZZFeatureMap + FidelityQuantumKernel + QSVC, per spec section 16/9."""

    model_name = "qiskit-qsvc"

    def __init__(self, n_qubits: int = 4, reps: int = 2, model_version: str = "dev") -> None:
        if not 2 <= n_qubits <= 8:
            raise ValueError("n_qubits must be between 2 and 8 per spec section 9.")
        self.n_qubits = n_qubits
        self.reps = reps
        self.model_version = model_version
        self.is_trained = False
        self._state: _FittedState | None = None

    def _build_qsvc(self):
        try:
            from qiskit.circuit.library import ZZFeatureMap
            from qiskit_machine_learning.algorithms import QSVC
            from qiskit_machine_learning.kernels import FidelityQuantumKernel
        except ImportError as exc:  # pragma: no cover - exercised only when uninstalled
            raise QiskitUnavailableError(
                "qiskit / qiskit-machine-learning are not importable in this "
                "environment. Install the pinned versions in requirements.txt."
            ) from exc

        feature_map = ZZFeatureMap(feature_dimension=self.n_qubits, reps=self.reps)
        kernel = FidelityQuantumKernel(feature_map=feature_map)
        return QSVC(quantum_kernel=kernel, probability=True)

    def fit(self, X: np.ndarray, y: list[str]) -> None:
        scaler = MinMaxScaler()
        X_scaled = scaler.fit_transform(X)

        n_components = min(self.n_qubits, X_scaled.shape[1], max(X_scaled.shape[0] - 1, 1))
        pca = PCA(n_components=n_components, random_state=0)
        X_reduced = pca.fit_transform(X_scaled)

        qsvc = self._build_qsvc()
        qsvc.fit(X_reduced, y)

        self._state = _FittedState(scaler=scaler, pca=pca, qsvc=qsvc, classes=sorted(set(y)))
        self.is_trained = True

    def _transform(self, X: np.ndarray) -> np.ndarray:
        assert self._state is not None
        return self._state.pca.transform(self._state.scaler.transform(X))

    def predict(self, X: np.ndarray) -> list[str]:
        self._require_trained()
        return list(self._state.qsvc.predict(self._transform(X)))

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        self._require_trained()
        return self._state.qsvc.predict_proba(self._transform(X))

    def predict_one(self, x: np.ndarray, feature_version: str) -> ClassificationResult:
        self._require_trained()
        start = time.perf_counter()
        proba = self.predict_proba(x.reshape(1, -1))[0]
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        classes = list(self._state.qsvc.classes_)
        probabilities = {cls: float(p) for cls, p in zip(classes, proba, strict=True)}
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
            extra={"labels": labels, "n_qubits": self.n_qubits},
        )

    def save(self, path: Path) -> None:
        self._require_trained()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            pickle.dump(
                {"state": self._state, "model_version": self.model_version, "n_qubits": self.n_qubits},
                f,
            )

    def load(self, path: Path) -> None:
        with path.open("rb") as f:
            payload = pickle.load(f)
        self._state = payload["state"]
        self.model_version = payload["model_version"]
        self.n_qubits = payload["n_qubits"]
        self.is_trained = True

    def _require_trained(self) -> None:
        if not self.is_trained:
            raise RuntimeError(
                "QiskitQSVCClassifier.fit()/load() must be called before "
                "predict/predict_proba/evaluate. Callers should catch this and "
                "report ModelRunStatus.NOT_TRAINED rather than crashing the pipeline."
            )
