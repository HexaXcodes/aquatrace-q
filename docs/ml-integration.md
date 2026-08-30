# ML Integration Guide (for Shaun + Shashank)

Your integration surface is exactly three interfaces in `app/ml/base.py`,
`app/ml/feature_extractor.py`, and `app/ml/classical_classifier.py`. Nothing
in `app/api/`, `app/services/`, or the database schema needs to change when
you plug in a real model.

## 1. Detection / segmentation model

Implement `DetectionModel` (or `SegmentationModel`) from `app/ml/base.py`:

```python
class YourDetectionModel(DetectionModel):
    model_name = "your-model-name"
    model_version = "1.0.0"

    def predict(self, image_path: Path) -> list[RawDetection]:
        # load image_path, run your model, return:
        return [RawDetection(class_name="ANTHROPOGENIC", confidence=0.91, bbox=[x1, y1, x2, y2])]
```

Register it in `app/ml/model_registry.py`:

```python
@lru_cache
def get_detection_model() -> DetectionModel:
    return YourDetectionModel()   # was: FixtureThresholdDetector()
```

That's the entire integration. `detection_service.run_detection()` calls
`model.predict()` and persists whatever comes back — it does not care what's
inside `predict()`.

### E004: the real trained shipwreck segmentation model (now registered)

`app/ml/e004_detector.py`'s `E004ShipwreckDetector` is a genuine
`DetectionModel` implementation wrapping a trained Compact U-Net
(`app/ml/e004_unet.py`, copied verbatim from
`Shipwreck_TrainedModel/E004_AADVIK_HANDOFF/src/training/model.py`),
loaded from `models/E004_best.pt` (1.9M params, 1-channel 1024x1024
grayscale in, 1-channel logits out).

**Why `DetectionModel` and not `SegmentationModel`, even though E004 is a
segmenter:** `get_segmentation_model()` exists in `model_registry.py` but
nothing in `processing_service`'s DETECTING stage calls it —
`detection_service.run_detection()` only ever calls `get_detection_model()`.
Rather than adding a new orchestration stage, `E004ShipwreckDetector` runs
the U-Net internally, thresholds the output mask at `sigmoid(logits) > 0.5`,
connected-component-labels it (`scipy.ndimage`, same technique
`FixtureThresholdDetector` already uses), and turns each component into a
`RawDetection`: `bbox` from the component's bounding box, `mask_path`
pointing at a saved crop of that component's mask (under
`OUTPUT_DIRECTORY/e004_masks/`), `confidence` as the mean sigmoid
probability over the component's pixels, `class_name="shipwreck"` (a valid
`KNOWN_DEBRIS_SUBCLASSES` entry, `app/models/enums.py`).

**Registration is gated on checkpoint presence**, mirroring
`get_classical_classifier()`'s pattern exactly: if
`MODEL_DIRECTORY/E004_best.pt` exists, `get_detection_model()` loads and
returns `E004ShipwreckDetector`; otherwise (checkpoint absent, or torch not
importable — `TorchUnavailableError`) it falls back to
`FixtureThresholdDetector`, same honest-fallback shape used everywhere else
in this project. No new settings flag was added for this — `ML_MODEL_VERSION`
was considered (per this function's original docstring) but file-existence
gating is already this codebase's established convention for "is a real
model available," so a second, redundant flag seemed like the wrong call.
`tests/conftest.py` already redirects `MODEL_DIRECTORY` to an empty tmp dir
for every test, so the full existing suite keeps exercising the fixture
path unmodified; `tests/test_e004_detector.py` adds dedicated coverage for
the new adapter (skipped, not failed, if the checkpoint/torch aren't present
— `models/*` is gitignored, so a fresh clone without the handoff artifact
still passes the suite).

**Preprocessing — an inference-time design decision, not something copied
from training code.** `E004_AADVIK_HANDOFF/src/training/dataset.py` (the
authoritative source for how E004 was actually trained) has *no* resize/pad
logic: it only accepts pre-tiled, exact 1024x1024 image/mask pairs and
normalizes via `/255.0`. Real uploaded sonar images are arbitrary sizes, so
downsampling a whole image to 1024x1024 would shrink shipwreck shapes to a
different apparent scale than the native-resolution tiles E004 was trained
on. `E004ShipwreckDetector` instead **tiles** the input into non-overlapping
1024x1024 windows (zero-padding the final row/column of tiles), runs
inference per tile restricted to each tile's real (non-padded) region, and
stitches per-tile detections back into original-image pixel coordinates.
This preserves native pixel scale but means an object straddling a tile
boundary can be split into two detections — a known limitation on top of
the small-shipwreck one below, not yet mitigated with overlapping tiles.

**Real validated metrics** (measured by the model's authors; see
`Shipwreck_TrainedModel/E004_AADVIK_HANDOFF/README.md` — cited here, not
re-derived): **Mean Dice 0.677, IoU 0.652, Precision 0.700, Recall 0.672**
overall, on 396 validation samples.

**Known weakness — small shipwrecks (same honesty standard as the
train/serve gap below):** performance is *not* uniform across target size.

| Size | Samples | Dice | IoU | Precision | Recall |
|---|---|---|---|---|---|
| Small | 41 | **0.269** | 0.189 | 0.381 | 0.242 |
| Medium | 33 | 0.684 | 0.540 | 0.757 | 0.693 |
| Large | 11 | 0.681 | 0.523 | 0.858 | 0.585 |

E004 should **not** be represented as reliably detecting small shipwrecks —
Dice drops from ~0.68 on medium/large targets to 0.27 on small ones. Do not
quote the 0.677 overall Dice as if it applied uniformly across target sizes.
Per-image detail: `Shipwreck_TrainedModel/E004_AADVIK_HANDOFF/experiments/e004_small_shipwreck_eval/e004_per_image_results.csv`.
(A related experiment, E005, tried oversampling small shipwrecks
specifically and did *worse* overall — best Dice 0.594 vs. E004's 0.677 —
which is why E004, not E005, is the handoff model. See the handoff
README's "E005 NOTE" section.)

**A gap this integration surfaced, not fixed — read this before assuming
"shipwreck" detections stay labelled "shipwreck":** `E004ShipwreckDetector`
emits `class_name="shipwreck"` on each `RawDetection`, and
`target_service.create_targets_from_detections()` was extended (see its
`_SUBCLASS_CLASS_NAMES` map) to seed the new `Target.debris_subclass` with
that value at creation time. But `classification_service._apply_classical_result_to_target()`
**unconditionally overwrites** `Target.classification` /
`.debris_subclass` with whatever the classical classifier predicts, once
that classifier is trained (`run_status in {OK, TEST_FIXTURE}`) — by
design, per that module's own docstring ("updated from the classical
result only"). The currently-trained `models/classical_classifier.joblib`
was fit on the public Marine Debris FLS benchmark (`background`, `tire`,
`chain`, `propeller`, `can`, `bottle` — see the "Current training status"
section below): **it has never seen a "shipwreck" example and cannot
predict that label.** Confirmed live: running a real synthetic
shipwreck-shaped image through the full survey→upload→process pipeline
with E004 registered, the DETECTING stage correctly found it
(`class_name="shipwreck"`, `confidence=0.987`, a tight bbox around the
painted shape) — but the CLASSIFYING stage then overwrote the target to
`classification=NATURAL_SEABED`, `debris_subclass="natural_seabed"`,
which `priority_service.compute_priority()`'s `is_confident_natural` check
would then route to `IGNORE`. This isn't a bug introduced by this
integration — every detector's bootstrap classification has always been
subject to being overwritten this way, including `FixtureThresholdDetector`'s
generic `"ANTHROPOGENIC"` — but E004 is the first detector to emit a
*specific, meaningful* subclass, which makes the loss visible and
consequential for the first time. Fixing it is out of scope here (it needs
either real shipwreck-labelled feature training data for the classical
classifier — Shashank's dataset to supply — or a product decision about
whether `classification_service` should ever downgrade a detector's own
class signal); flagging it clearly instead of silently letting E004's
signal get thrown away.

## 2. Feature extraction

`FeatureExtractor` in `app/ml/feature_extractor.py`. The currently-registered
`StatisticalFeatureExtractor` computes hand-engineered features; a learned
embedding extractor (e.g. a PyTorch CNN) implements the same interface:

```python
class YourEmbeddingExtractor(FeatureExtractor):
    feature_version = "cnn-embed-v1"

    def extract(self, image_path: Path, bbox: list[float] | None) -> ExtractedFeatures:
        # crop, run your model, return the embedding vector
        return ExtractedFeatures(feature_version=self.feature_version, values=embedding.tolist(), names=[...])
```

`feature_service.extract_and_store_features()` takes an `extractor` argument
— swap it there, or change the module-level default.

## 3. Classical classifier

`ClassicalClassifier` in `app/ml/classical_classifier.py` already has a real,
working `SklearnClassicalClassifier` (logistic regression by default, or pass
any scikit-learn-compatible estimator). Your job with real labelled data:

```python
classifier = SklearnClassicalClassifier(model_version="v1")
classifier.fit(X_train, y_train)
classifier.save(settings.MODEL_DIRECTORY / "classical_classifier.joblib")
```

Once that file exists, `model_registry.get_classical_classifier()` loads it
automatically on next startup — `is_trained` flips to `True`, and
`classification_service` starts reporting `run_status = OK` instead of
`NOT_TRAINED`. No code change needed for this path; it's already wired.

## Current training status (not yet Shashank's real dataset)

`models/classical_classifier.joblib` has been trained — but on the public
[Marine Debris FLS Dataset](https://github.com/mvaldenegro/marine-debris-fls-datasets)
(real ARIS Explorer 3000 forward-looking-sonar crops: can/bottle/chain/
propeller/tire/background), not on this project's own labelled data, which
doesn't exist yet. `scripts/build_fls_training_data.py` builds the CSV,
`scripts/train_classical_classifier.py` trains and saves it. This proves the
training pipeline works end-to-end against real (if generic-benchmark)
sonar data, and gives `classification_service` something real to report
instead of `NOT_TRAINED` — it is not a claim that the model is tuned for
this project's actual reef-debris use case.

**Held-out accuracy on that benchmark: 76.7%.** Do not quote this number as
"real-world accuracy" anywhere (docs, pitch deck, to judges) — it's clean
benchmark accuracy on the dataset's own pre-cropped, centered 96x96 images.
Live-testing it through the actual pipeline surfaced a real train/serve gap:
the benchmark hands the classifier a clean, human-curated crop, but
`FixtureThresholdDetector` produces its own tighter, offset bounding box via
intensity thresholding — a different input distribution than what the model
was trained on. Confirmed directly: a real tire crop, run through the full
survey→upload→process pipeline, came back classified as `propeller`; a real
background crop threw two false debris detections. The honest framing is
"76.7% on a clean benchmark, with a known train/serve distribution gap not
yet quantified on live-detected crops" — not "76.7% accurate."

This gap should also be expected to move, in either direction, once a real
`DetectionModel` (this section) replaces `FixtureThresholdDetector` — the
mismatch exists specifically because the fixture's discovered boxes don't
match the benchmark's curation convention, and a real trained detector may
behave quite differently. Worth keeping in mind rather than being
surprised when the number changes later.

## Feature versioning

Every `FeatureVector` and `ClassificationRecord` records `feature_version`.
If you change what `extract()` returns (new features, different
normalization), bump `feature_version` — this lets old classification
records stay honestly attributed to the feature representation they were
actually computed from.

## What you should NOT need to touch

`app/api/v1/detections.py`, `targets.py`, `classification.py`, the database
migrations, or anything in `app/services/` other than swapping which model
instance `model_registry` returns.
