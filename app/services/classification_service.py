"""
Classification service (Phases 8-10).

Runs the registered classical classifier (always attempted) and the
registered quantum classifier (attempted only if `QML_ENABLED` and
importable), and writes one `ClassificationRecord` per stage that was
attempted -- including rows whose `run_status` is `NOT_TRAINED` or
`UNAVAILABLE`, which have `predicted_class = None` rather than a
fabricated guess.

`Target.classification` / `.confidence` / `.debris_subclass` /
`.uncertainty` are updated from the **classical** result only. The
quantum result is stored purely as a comparison data point (spec
section 17/49: quantum classifies with an uncertainty estimate, it does
not unilaterally become the system's ecological-risk input, and no
quantum-advantage claim is made anywhere in this service).
"""

from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.ml.model_registry import get_classical_classifier, get_quantum_classifier
from app.models.classification import ClassificationRecord
from app.models.enums import ModelRunStatus, ModelStage, TargetClass
from app.models.feature_vector import FeatureVector
from app.models.target import Target
from app.services.uncertainty_service import compute_uncertainty

logger = get_logger(__name__)

_SUBCLASS_TO_TARGET_CLASS: dict[str, TargetClass] = {
    "natural_seabed": TargetClass.NATURAL_SEABED,
}


def classify_target(
    db: Session, target: Target, feature_vector: FeatureVector
) -> tuple[ClassificationRecord, ClassificationRecord]:
    """Run classical then quantum classification for `target`. Returns
    (classical_record, quantum_record); the quantum record has
    `run_status in {NOT_TRAINED, UNAVAILABLE}` when no trained quantum
    model is available."""
    X = np.array(feature_vector.values, dtype=np.float64)

    classical_record = _run_classical(db, target, feature_vector, X)
    quantum_record = _run_quantum(db, target, feature_vector, X)

    if classical_record.run_status in (ModelRunStatus.OK, ModelRunStatus.TEST_FIXTURE):
        _apply_classical_result_to_target(db, target, classical_record)

    db.commit()
    db.refresh(target)
    return classical_record, quantum_record


def _run_classical(
    db: Session, target: Target, feature_vector: FeatureVector, X: np.ndarray
) -> ClassificationRecord:
    classifier = get_classical_classifier()

    if not classifier.is_trained:
        record = ClassificationRecord(
            target_id=target.id,
            feature_vector_id=feature_vector.id,
            stage=ModelStage.CLASSICAL,
            run_status=ModelRunStatus.NOT_TRAINED,
            model_name=classifier.model_name,
            model_version=classifier.model_version,
            feature_version=feature_vector.feature_version,
            note="No trained classical classifier is registered yet.",
        )
    else:
        result = classifier.predict_one(X, feature_vector.feature_version)
        record = ClassificationRecord(
            target_id=target.id,
            feature_vector_id=feature_vector.id,
            stage=ModelStage.CLASSICAL,
            run_status=ModelRunStatus.OK,
            predicted_class=result.predicted_class,
            probabilities=result.probabilities,
            confidence=result.confidence,
            model_name=result.model_name,
            model_version=result.model_version,
            feature_version=result.feature_version,
            inference_time_ms=result.inference_time_ms,
        )

    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _run_quantum(
    db: Session, target: Target, feature_vector: FeatureVector, X: np.ndarray
) -> ClassificationRecord:
    classifier = get_quantum_classifier()

    if classifier is None:
        record = ClassificationRecord(
            target_id=target.id,
            feature_vector_id=feature_vector.id,
            stage=ModelStage.QUANTUM,
            run_status=ModelRunStatus.UNAVAILABLE,
            model_name="qiskit-qsvc",
            model_version="n/a",
            feature_version=feature_vector.feature_version,
            note="QML disabled or qiskit/qiskit-machine-learning not importable.",
        )
    elif not classifier.is_trained:
        record = ClassificationRecord(
            target_id=target.id,
            feature_vector_id=feature_vector.id,
            stage=ModelStage.QUANTUM,
            run_status=ModelRunStatus.NOT_TRAINED,
            model_name=classifier.model_name,
            model_version=classifier.model_version,
            feature_version=feature_vector.feature_version,
            note="No trained QuantumClassifier is registered yet.",
        )
    else:
        result = classifier.predict_one(X, feature_vector.feature_version)
        record = ClassificationRecord(
            target_id=target.id,
            feature_vector_id=feature_vector.id,
            stage=ModelStage.QUANTUM,
            run_status=ModelRunStatus.OK,
            predicted_class=result.predicted_class,
            probabilities=result.probabilities,
            confidence=result.confidence,
            model_name=result.model_name,
            model_version=result.model_version,
            feature_version=result.feature_version,
            inference_time_ms=result.inference_time_ms,
        )

    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _apply_classical_result_to_target(
    db: Session, target: Target, record: ClassificationRecord
) -> None:
    assert record.probabilities is not None and record.predicted_class is not None

    uncertainty = compute_uncertainty(record.probabilities)
    target.debris_subclass = record.predicted_class
    target.classification = _SUBCLASS_TO_TARGET_CLASS.get(record.predicted_class, TargetClass.ANTHROPOGENIC)
    target.confidence = record.confidence
    target.uncertainty = uncertainty.score
    db.add(target)
