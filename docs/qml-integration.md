# QML Integration Guide (for Aadvik)

`app/ml/quantum_classifier.py` already implements the real pipeline end to
end — this is not a stub you need to build from scratch:

```
feature vector → MinMaxScaler → PCA(≤8 dims) → ZZFeatureMap
              → FidelityQuantumKernel → QSVC → probabilities
```

`QiskitQSVCClassifier` genuinely runs this on Qiskit's statevector simulator
(no hardware backend configured — none is needed for a kernel classifier at
this scale). It has been executed and verified in this environment,
including `fit`/`predict`/`predict_proba`/`evaluate`/`save`/`load` and a
save→reload→predict round-trip (see `tests/test_quantum.py`).

## Current training status (not yet Shashank's real dataset)

`models/quantum_classifier.pkl` has been trained — but on the public
[Marine Debris FLS Dataset](https://github.com/mvaldenegro/marine-debris-fls-datasets)
(`scripts/build_fls_training_data.py` + `scripts/train_quantum_classifier.py`),
not on this project's own labelled data, which doesn't exist yet. Held-out
accuracy: **75.0%**, genuinely close to the classical classifier's 76.7% on
the same data — a real classical-vs-quantum comparison point, not a
synthetic one.

**Do not quote 75% as real-world accuracy.** Same caveat as
`docs/ml-integration.md`: it's clean benchmark accuracy on pre-cropped,
centered crops, and live-testing through the full pipeline surfaced a real
train/serve distribution gap against `FixtureThresholdDetector`'s own
discovered bounding boxes (see that doc for the concrete examples). The
honest framing is "75% on a clean benchmark, with a known train/serve gap
not yet quantified on live-detected crops."

That dataset is still yours to build once Shashank's feature pipeline is
producing real project-specific embeddings, and once a real `DetectionModel`
replaces the fixture (which will likely move this number). Training on new
data:

```python
from app.ml.quantum_classifier import QiskitQSVCClassifier

classifier = QiskitQSVCClassifier(n_qubits=4, model_version="v1")
classifier.fit(X_train, y_train)   # X_train: real feature vectors, y_train: real labels
classifier.save(settings.MODEL_DIRECTORY / "quantum_classifier.pkl")
```

Once `quantum_classifier.pkl` exists, `model_registry.get_quantum_classifier()`
loads it automatically — `classification_service` starts reporting
`run_status = OK` for the quantum stage instead of `NOT_TRAINED`.

## Tuning knobs (all in `Settings`, not hardcoded)

- `QML_FEATURE_DIMENSIONS` (default 4): PCA target dimensionality / qubit count.
  Valid range enforced in code: 2-8 (spec section 9).
- `QML_ENABLED` (default true): flips the registry to always return `None`
  (`ModelRunStatus.UNAVAILABLE`) if you need to disable QML entirely, e.g. a
  deployment without qiskit installed.

## Classical vs quantum comparison

`POST /api/v1/experiments/classification` (see `app/services/experiment_service.py`)
trains a fresh classical classifier and a fresh quantum classifier on a
caller-supplied labelled dataset, evaluates both on a held-out split, and
returns real, measured accuracy/precision/recall/F1/confusion-matrix for
each — with `quantum_status = UNAVAILABLE` and `quantum_metrics = null` if
qiskit isn't importable in that deployment. **No comparison in this codebase
ever concludes or implies a quantum advantage** — that's a conclusion for
you to draw from the numbers, backed by a real experiment, not something the
API asserts.

## Known deprecation warnings (harmless, tracked)

The pinned versions (`qiskit==1.3.1`, `qiskit-machine-learning==0.8.2`) emit
`PendingDeprecationWarning`/`DeprecationWarning` for `ZZFeatureMap` and the
V1 `Sampler` primitive. These are warnings, not errors — the pipeline is
fully functional (verified by `tests/test_quantum.py`). Upgrading to
Qiskit's V2 primitives (`StatevectorSampler`) and the `z_feature_map`
function is a self-contained follow-up, not a blocker.

## What you should NOT need to touch

The database schema, `classification_service.py`'s control flow, or any API
route — `QiskitQSVCClassifier` is already the full integration boundary.
