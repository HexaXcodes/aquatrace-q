"""
Builds a labelled training CSV from the public Marine Debris FLS Dataset
(Valdenegro-Toro et al., watertank-class release -- real ARIS Explorer
3000 forward-looking-sonar crops), run through the actual
StatisticalFeatureExtractor code path, in the same CSV shape
train_classical_classifier.py / train_quantum_classifier.py expect.

Download the dataset first (not included in this repo -- ~29MB, no
registration needed):
    https://github.com/mvaldenegro/marine-debris-fls-datasets/releases/download/watertank-class-v1.0/marine-debris-watertank-classification-96x96.hdf5

Requires h5py (not in requirements.txt -- only needed for this one-off
import, not the running app): pip install h5py

The dataset's "background" class is relabelled to "natural_seabed" here,
not left as-is: classification_service._SUBCLASS_TO_TARGET_CLASS maps
that exact string to TargetClass.NATURAL_SEABED; every other string
(including the literal "background") falls through to ANTHROPOGENIC,
which would silently mislabel every non-debris sample.

Usage:
    python scripts/build_fls_training_data.py path/to/marine-debris-watertank-classification-96x96.hdf5
    python scripts/build_fls_training_data.py <path> --samples-per-class 40 --classes background,tire,chain
"""

from __future__ import annotations

import argparse
import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `app.*` imports work

import h5py
import numpy as np
from PIL import Image

from app.ml.feature_extractor import StatisticalFeatureExtractor

DEFAULT_CLASSES = ["background", "tire", "chain", "propeller", "can", "bottle"]
LABEL_OVERRIDES = {"background": "natural_seabed"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hdf5_path", type=Path, help="Path to the downloaded .hdf5 file")
    parser.add_argument(
        "--classes",
        default=",".join(DEFAULT_CLASSES),
        help=f"Comma-separated class names to include (default: {','.join(DEFAULT_CLASSES)})",
    )
    parser.add_argument("--samples-per-class", type=int, default=40)
    parser.add_argument("--output", default="data/real_fls_training_data.csv")
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    classes_wanted = [c.strip() for c in args.classes.split(",") if c.strip()]
    rng = np.random.default_rng(args.seed)
    extractor = StatisticalFeatureExtractor()

    with h5py.File(args.hdf5_path, "r") as f:
        class_names = [c.decode() if isinstance(c, bytes) else c for c in f["class_names"][:]]
        x_train = f["x_train"][:]
        y_train = f["y_train"][:]

    unknown = set(classes_wanted) - set(class_names)
    if unknown:
        raise SystemExit(f"Unknown class name(s) {unknown}. Available: {class_names}")

    class_to_idx = {name: i for i, name in enumerate(class_names)}
    rows: list[list] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for cls in classes_wanted:
            idx = class_to_idx[cls]
            candidates = np.where(y_train == idx)[0]
            n = min(args.samples_per_class, len(candidates))
            if n < args.samples_per_class:
                print(f"Warning: only {n} samples available for '{cls}' (asked for {args.samples_per_class})")
            chosen = rng.choice(candidates, size=n, replace=False)

            label = LABEL_OVERRIDES.get(cls, cls)
            for i, sample_idx in enumerate(chosen):
                arr = x_train[sample_idx, :, :, 0]  # (H, W), float32 in [0, ~1]
                pixel_arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
                img_path = tmp_path / f"{cls}_{i}.png"
                Image.fromarray(pixel_arr, mode="L").save(img_path)

                features = extractor.extract(img_path, bbox=None)
                rows.append([*features.values, label])

        feature_names = extractor.extract(list(tmp_path.glob("*.png"))[0], None).names

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([*feature_names, "label"])
        writer.writerows(rows)

    labels_used = sorted({row[-1] for row in rows})
    print(f"Wrote {len(rows)} real feature vectors ({labels_used}) to {output_path}")
    if "background" in classes_wanted:
        print("Note: 'background' relabelled to 'natural_seabed' to match classification_service's mapping.")


if __name__ == "__main__":
    main()
