"""
Trains QiskitQSVCClassifier on a labelled feature CSV (same format as
train_classical_classifier.py) and saves it to
MODEL_DIRECTORY/quantum_classifier.pkl, where model_registry.py's
get_quantum_classifier() picks it up on the next app restart.

This runs a real quantum-kernel simulation (FidelityQuantumKernel + QSVC)
locally -- no hardware involved, but genuinely slower than the classical
classifier: kernel evaluation is O(n^2) circuit simulations. Expect
seconds on a few dozen samples, not milliseconds; --n-qubits and --reps
both push training time up further, which is worth knowing before real
(larger) data arrives.

Usage:
    python scripts/train_quantum_classifier.py data/synthetic_training_data.csv
    python scripts/train_quantum_classifier.py data/synthetic_training_data.csv --n-qubits 6 --reps 3
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `app.*` imports work

import numpy as np
from sklearn.model_selection import train_test_split

from app.core.config import get_settings
from app.ml.quantum_classifier import QiskitQSVCClassifier, QiskitUnavailableError

METADATA_COLUMNS = {"target_id", "survey_id", "feature_version", "label"}


def load_dataset(csv_path: Path) -> tuple[np.ndarray, list[str]]:
    with csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise SystemExit(f"{csv_path} has no header row.")
        feature_columns = [c for c in reader.fieldnames if c not in METADATA_COLUMNS]

        X: list[list[float]] = []
        y: list[str] = []
        skipped = 0
        for row in reader:
            label = (row.get("label") or "").strip()
            if not label:
                skipped += 1
                continue
            X.append([float(row[c]) for c in feature_columns])
            y.append(label)

    if skipped:
        print(f"Skipped {skipped} unlabeled row(s).")
    if len(X) < 4:
        raise SystemExit(
            f"Only {len(X)} labeled row(s) in {csv_path} -- need at least a handful per class."
        )
    return np.array(X, dtype=np.float64), y


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, help="Labelled feature CSV")
    parser.add_argument("--n-qubits", type=int, default=4, help="2-8, per QiskitQSVCClassifier")
    parser.add_argument("--reps", type=int, default=2, help="ZZFeatureMap repetitions")
    parser.add_argument("--model-version", default="dev")
    parser.add_argument("--test-size", type=float, default=0.25)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    X, y = load_dataset(args.csv_path)

    classes = sorted(set(y))
    if len(classes) < 2:
        raise SystemExit(f"Only one class ({classes}) present -- need at least two to train.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=0, stratify=y
    )

    try:
        clf = QiskitQSVCClassifier(
            n_qubits=args.n_qubits, reps=args.reps, model_version=args.model_version
        )
    except QiskitUnavailableError as exc:
        raise SystemExit(str(exc)) from exc

    print(f"Training on {len(X_train)} samples, n_qubits={args.n_qubits}, reps={args.reps} ...")
    start = time.perf_counter()
    clf.fit(X_train, y_train)
    print(f"Fit took {time.perf_counter() - start:.1f}s")

    metrics = clf.evaluate(X_test, y_test)
    eval_seconds = metrics.inference_time_ms / 1000
    print(
        f"Held-out accuracy: {metrics.accuracy:.3f}  f1: {metrics.f1:.3f}  "
        f"n_test={metrics.sample_count}  (eval took {eval_seconds:.1f}s)"
    )
    print(f"Classes: {classes}")
    print(f"Confusion matrix (labels={metrics.extra['labels']}):")
    for row in metrics.confusion_matrix:
        print(f"  {row}")

    settings = get_settings()
    out_path = settings.MODEL_DIRECTORY / "quantum_classifier.pkl"
    clf.save(out_path)
    print(f"Saved to {out_path} -- restart the app for model_registry to pick it up.")


if __name__ == "__main__":
    main()
