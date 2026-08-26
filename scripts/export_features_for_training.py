"""
Exports FeatureVector rows from the database to a CSV that a human (or a
teammate with the real dataset) can open, fill in the `label` column for,
and hand back to train_classical_classifier.py / train_quantum_classifier.py.

Without --survey-id, exports the latest feature vector per target across
every survey in the database (a target can accumulate several feature
vectors across reprocessing runs). With --survey-id, scopes to one survey.

Usage:
    python scripts/export_features_for_training.py
    python scripts/export_features_for_training.py --survey-id <id>
    python scripts/export_features_for_training.py --output data/export.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `app.*` imports work

from sqlalchemy import select

# Importing app.db.base (not just the two models used directly below)
# registers every ORM model with SQLAlchemy's declarative mapper registry
# before any query runs. Target.detection has a string-based
# relationship("Detection"), resolved lazily on first use -- skip this
# import and mapper configuration fails with "failed to locate a name
# ('Detection')" the moment a query actually executes.
from app.db.base import FeatureVector, Target  # noqa: F401
from app.db.session import get_session_factory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survey-id", default=None, help="Only export targets from this survey")
    parser.add_argument(
        "--output", default="data/features_for_labeling.csv", help="Output CSV path"
    )
    return parser.parse_args()


def latest_feature_vector_per_target(db, survey_id: str | None) -> list[tuple[Target, FeatureVector]]:
    query = select(Target)
    if survey_id:
        query = query.where(Target.survey_id == survey_id)
    targets = db.execute(query).scalars().all()

    results: list[tuple[Target, FeatureVector]] = []
    for target in targets:
        fv = db.execute(
            select(FeatureVector)
            .where(FeatureVector.target_id == target.id)
            .order_by(FeatureVector.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if fv is not None:
            results.append((target, fv))
    return results


def main() -> None:
    args = parse_args()
    db = get_session_factory()()

    try:
        pairs = latest_feature_vector_per_target(db, args.survey_id)
    finally:
        db.close()

    if not pairs:
        print("No feature vectors found. Run a survey through /process first.")
        return

    # Canonical column order comes from the first row's feature_names --
    # every FeatureVector produced by the same extractor version should
    # match; rows with a different dimensionality (e.g. after changing the
    # extractor mid-dataset) are flagged and skipped rather than silently
    # misaligned.
    feature_names = pairs[0][1].feature_names
    if feature_names is None:
        feature_names = [f"feature_{i}" for i in range(len(pairs[0][1].values))]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    skipped = 0
    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        # target_id/survey_id/feature_version are metadata, not features --
        # train_classical_classifier.py / train_quantum_classifier.py both
        # know to skip them by name when loading this file.
        writer.writerow(["target_id", "survey_id", "feature_version", *feature_names, "label"])

        for target, fv in pairs:
            if len(fv.values) != len(feature_names):
                skipped += 1
                continue
            # "label" is left blank -- fill it in before training.
            writer.writerow([target.id, target.survey_id, fv.feature_version, *fv.values, ""])

    print(f"Exported {len(pairs) - skipped} rows to {output_path}")
    if skipped:
        print(f"Skipped {skipped} rows with mismatched feature dimensions (different feature_version?)")
    print("Fill in the 'label' column, then feed this file to the training scripts.")


if __name__ == "__main__":
    main()
