# E004 — Aadvik Handoff

## Purpose

This package contains the verified E004 shipwreck segmentation model
and the implementation/evaluation files required for backend integration
and model verification.

---

## MODEL

Experiment:
E004

Architecture:
Compact U-Net

Parameters:
1,942,289

Input:
1-channel grayscale image

Input resolution:
1024 x 1024

Output:
1-channel binary segmentation mask

Checkpoint:
experiments/checkpoints/E004_best.pt

IMPORTANT:
Use E004_best.pt.

Do NOT substitute Epoch-20 weights.

---

## E004 VALIDATION DATASET

Valid training samples:
1637

Malformed training pairs excluded:
16

Valid validation samples:
396

Malformed validation pairs excluded:
6

All samples fed to the model:
1024 x 1024

---

## E004 OVERALL VALIDATION RESULTS

Mean Dice:
0.6770

Mean IoU:
0.6523

Mean Precision:
0.6996

Mean Recall:
0.6723

---

## E004 PERFORMANCE BY SHIPWRECK SIZE

EMPTY
Samples: 311
Dice: 0.7299
IoU: 0.7299
Precision: 0.7299
Recall: 0.7299

SMALL
Samples: 41
Dice: 0.2690
IoU: 0.1888
Precision: 0.3812
Recall: 0.2422

MEDIUM
Samples: 33
Dice: 0.6835
IoU: 0.5397
Precision: 0.7573
Recall: 0.6929

LARGE
Samples: 11
Dice: 0.6811
IoU: 0.5226
Precision: 0.8580
Recall: 0.5852

---

## IMPORTANT SMALL-SHIPWRECK LIMITATION

E004 was specifically evaluated for small shipwreck detection.

The validation results show substantially weaker performance on small
shipwrecks than on medium/large shipwrecks.

Therefore E004 should NOT be represented as reliably detecting extremely
small shipwrecks.

The detailed per-image evaluation is provided in:

experiments/e004_small_shipwreck_eval/e004_per_image_results.csv

---

## FILES

experiments/checkpoints/E004_best.pt
    Trained E004 model checkpoint.

experiments/e004_small_shipwreck_eval/e004_per_image_results.csv
    Per-image E004 validation evaluation.

src/training/model.py
    Compact U-Net architecture.

src/training/dataset.py
    Dataset loading implementation.

src/training/losses.py
    E004 BCEDiceLoss implementation.

src/training/train.py
    Training/metric implementation.

---

## BACKEND INTEGRATION

The backend should:

1. Load E004_best.pt.
2. Convert the incoming side-scan sonar image to the expected
   single-channel input representation.
3. Provide a 1024 x 1024 input to the model.
4. Run inference.
5. Apply the project's existing output/post-processing logic.
6. Return the resulting segmentation information.

Do not assume that the model outputs bounding boxes.
E004 is a binary segmentation model and outputs a segmentation mask.

---

## E005 NOTE

E005 was an experimental targeted small-shipwreck oversampling run.

E005 achieved:

Best validation Dice: 0.5935

Its small-shipwreck evaluation was:

Very Small Dice: 0.0916
Small Dice: 0.4317
Medium Dice: 0.5455
Large Dice: 0.5600

E005 therefore did not replace E004 as the handoff model.

The handoff model is E004_best.pt.

---

## HANDOFF RULE

For backend integration, use:

experiments/checkpoints/E004_best.pt

This package intentionally does not include the full dataset or unrelated
experimental files.
