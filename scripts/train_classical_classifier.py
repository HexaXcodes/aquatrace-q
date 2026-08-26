"""
Trains SklearnClassicalClassifier on a labelled feature CSV (from
generate_synthetic_training_data.py, or export_features_for_training.py
with the `label` column filled in) and saves it to
MODEL_DIRECTORY/classical_classifier.joblib, where model_registry.py's
get_classical_classifier() picks it up on the next app restart.

Usage:
    python scripts/train_classical_classifier.py data/synthetic_training_data.csv
    python scripts/train_classical_classifier.py data/features_for_labeling.csv --model-version v1
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `app.*` imports work

import numpy as np
from sklearn.model_selection import train_test_split

from app.core.config import get_settings
from app.ml.classical_classifier import SklearnClassicalClassifier

# Columns export_features_for_training.py adds that aren't feature values --
# every other column is treated as a feature, in file order, so this loader
# works unmodified against both scripts' output.
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

    clf = SklearnClassicalClassifier(model_version=args.model_version)
    clf.fit(X_train, y_train)

    metrics = clf.evaluate(X_test, y_test)
    print(f"Held-out accuracy: {metrics.accuracy:.3f}  f1: {metrics.f1:.3f}  n_test={metrics.sample_count}")
    print(f"Classes: {classes}")
    print(f"Confusion matrix (labels={metrics.extra['labels']}):")
    for row in metrics.confusion_matrix:
        print(f"  {row}")

    settings = get_settings()
    out_path = settings.MODEL_DIRECTORY / "classical_classifier.joblib"
    clf.save(out_path)
    print(f"Saved to {out_path} -- restart the app for model_registry to pick it up.")


if __name__ == "__main__":
    main()
