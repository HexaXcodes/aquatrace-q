# ML Integration Guide (for Shaun + Shashank)

Your integration surface is exactly three interfaces in `app/ml/base.py`,
`app/ml/feature_extractor.py`, and `app/ml/classical_classifier.py`. No API
route file (`app/api/v1/*.py`) needs to change when you plug in a real
model. In practice, both real integrations so far (E004, YOLO11s -- see
below) *did* each need one or two small, deliberate `app/services/`
changes (never routes) and, once, a real migration -- see "What you should
NOT need to touch" at the end of this file for exactly what changed and
why. The registry (`app/ml/model_registry.py`) is still the one place that
*always* changes.

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
**Confirmed, not just theoretical:** a single synthetic shipwreck-shaped
blob centered exactly on a tile boundary (x=1024 in a 2048x1024 test image)
came back as two separate `RawDetection`s, `[925, 482, 1024, 542]` and
`[1024, 481, 1126, 544]` (confidence 0.943 and 0.988) — both bboxes meet
exactly at the seam, confirming this is a tiling artifact and not two real
objects. Low risk in practice for AI4Shipwrecks-scale imagery (most sonar
tiles are already ≤1024px on a side, so most real uploads never tile at
all), but worth knowing before a demo uses an image large enough to trigger
it.

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

**A gap this integration surfaced — the architecture-level half is now
fixed; the underlying data gap is not, and is a separate problem.**
`E004ShipwreckDetector` emits `class_name="shipwreck"` on each
`RawDetection`, and `target_service.create_targets_from_detections()`
seeds the new `Target.debris_subclass` with that value at creation time
(see its `_SUBCLASS_CLASS_NAMES` map). Originally,
`classification_service._apply_classical_result_to_target()`
**unconditionally overwrote** `Target.classification` / `.debris_subclass`
with whatever the classical classifier predicted, once that classifier was
trained — by design, per that module's docstring ("updated from the
classical result only"). The currently-trained
`models/classical_classifier.joblib` was fit on the public Marine Debris
FLS benchmark (`background`, `tire`, `chain`, `propeller`, `can`, `bottle`
— see "Current training status" below): it has never seen a "shipwreck"
example and cannot predict that label. Confirmed live, twice,
independently: once here against a synthetic shipwreck-shaped test image
(DETECTING found it at `class_name="shipwreck"`, confidence 0.987, a tight
bbox; CLASSIFYING then overwrote the target to
`classification=NATURAL_SEABED` at 100% reported confidence), and
separately by report against a real NOAA sonar image (SS Robert E. Lee) —
same failure mode, live in the actual UI: Target Details showed
"NATURAL_SEABED, 100.0% confidence" for a target E004 had itself flagged
as a shipwreck detection. A textbook closed-set classification failure —
the classifier was never given an "unknown/out-of-distribution" option, so
it forces a confident guess among the 6 classes it does know — which
`priority_service`'s `is_confident_natural` check would then route
straight to `IGNORE`.

**Fixed:** `classification_service.py` now has
`_detector_protected_class(target, classifier)`, checked before
`_apply_classical_result_to_target()` runs. It compares the target's
detector-seeded `debris_subclass` against `classifier.known_classes` — the
classifier's *actual* trained vocabulary (`ClassicalClassifier.known_classes`,
new abstract property), not an assumed one. If the classifier's vocabulary
doesn't include that subclass at all, its prediction is structurally
uninformed (it has zero training examples of that class) rather than a
real disagreement, so `Target.classification/debris_subclass/confidence`
are left as the detector reported instead of being overwritten. The
classical (and quantum) result is **always still written to
`ClassificationRecord` in full**, with a `note` explaining why it wasn't
promoted — nothing about this fix hides the disagreement, it only changes
which one is authoritative on `Target`. This self-corrects automatically
the moment the classifier's training data grows to include a real
"shipwreck" example (`known_classes` would then include it, and
`_detector_protected_class` naturally stops applying) — no further code
change needed here when that data arrives. Regression coverage:
`tests/test_features_classification.py::test_classifier_cannot_overwrite_a_class_it_was_never_trained_on`
and its mirror-image
`::test_classifier_can_overwrite_once_it_knows_the_detector_class`.

**Still open — a data problem, not a code problem:** the classical (and
quantum) classifier training data needs a labelled "shipwreck" class before
its prediction can ever be *correct* for shipwreck targets, not merely
non-overwriting. Until Shashank's dataset supplies real shipwreck-labelled
examples, expect every "shipwreck" target's `ClassificationRecord` to keep
showing a confident-but-wrong classical guess (`natural_seabed` or
whichever of the 6 FLS classes scores highest) — now correctly recorded as
non-authoritative instead of silently becoming the target's classification,
but still not an accurate classical opinion about shipwrecks. These are two
different problems: the overwrite behavior is an architecture bug (fixed);
the classifier not recognizing real shipwrecks is a training-data gap
(open, and this is now the strongest concrete case for prioritizing it).

**A "the fix doesn't work" report was investigated and NOT reproduced --
read this before assuming the fix above is broken.** A follow-up report
claimed the protection above wasn't engaging at all: 5 real shipwreck
targets in a live server, all still overwritten to `natural_seabed` or
`propeller` with no protective `note`. Investigated by re-reading
`_detector_protected_class()`/`known_classes` fresh against the live repo
(unchanged since the fix commit), then reproducing live four separate
ways: (1) a single target through the real `classify_target()` call path,
(2) five targets in one survey (matching the report's count) walked
through the same service calls `processing_service` uses, (3) five targets
through the actual `POST /surveys/{id}/process` API end-to-end via
`TestClient`, and (4) the same, again, over real HTTP against a genuinely
separate, already-running `uvicorn app.main:app` process (found already
listening on port 8000 -- not one started for this investigation) rather
than `TestClient`'s in-process ASGI transport. **All four protected
correctly, every time** -- `debris_subclass` stayed `"shipwreck"`, the
classical record's `note` correctly explained why it wasn't applied. No
code defect was found despite deliberately trying to break it on the exact
reported shape (multiple targets, one survey, one classify loop) and on a
real socket server, not just an in-process test client.

The timeline points to the actual explanation: the report's failing survey
was processed *6 minutes after* a verification run that succeeded on the
same on-disk code, both hours before the fix was even `git commit`-ed (the
commit just records already-working, already-tested code -- committing is
not what made it work). The only thing that plausibly differs between "a
freshly-started process" (which always re-imports the current file) and
"a request handled by a long-running `uvicorn app.main:app` process that
was already running before the fix was written" is that **Python does not
hot-reload edited source files in an already-running process** -- a server
started before an edit keeps executing the old bytecode for that module
until it's restarted (or run with `--reload`), regardless of what's on
disk. If you're testing a backend code change against a server you started
earlier in the session, **restart it** (or run with `uvicorn app.main:app
--reload` during development) before concluding a fix doesn't work.

This can't be fully proven after the fact (the specific process that
served that request is gone), so it's presented as the best-supported
explanation from the evidence available, not a certainty -- if it
recurs against a server confirmed to have been restarted after this
commit, that's a real bug and should be reported again with that
confirmation included. New regression coverage either way:
`tests/test_features_classification.py::test_protection_holds_against_the_real_registered_classifier`
exercises the *real* `model_registry.get_classical_classifier()` path
against the actually-loaded `models/classical_classifier.joblib` (skipped
if that gitignored artifact isn't present), closing the gap between "a
hand-built classifier in a test" and "what a real server actually loads"
that the two tests above didn't cover.

**Quantum was never in scope for this protection, and that's correct, not
a gap.** The same report noted quantum predictions
(`natural_seabed`/`can`/`natural_seabed`) also showing up for these
targets. By design, predating this fix entirely, `_run_quantum()`'s result
is *never* written to `Target` in either the pre-fix or post-fix code --
only `_apply_classical_result_to_target()` (classical-only) ever mutates
`Target.classification`/`.debris_subclass`. Quantum's `ClassificationRecord`
rows showing up alongside classical's are exactly the intended behavior
(comparison data point, never authoritative -- see this file's top
docstring and spec section 17/49), not evidence of a second overwrite bug.

### YOLO11s: the real trained marine debris/gear detector (now registered)

`app/ml/yolo_debris_detector.py`'s `YoloDebrisDetector` wraps a trained
YOLO11s object detector (`ultralytics==8.4.129`), loaded from
`models/yolo11s_marine_debris_best.pt`, trained for 60 epochs on real ARIS
Explorer 3000 forward-looking-sonar imagery from the same public
[Marine Debris FLS Dataset](https://github.com/mvaldenegro/marine-debris-fls-datasets)
already used for this project's classical/quantum classifier training data
(see "Current training status" below) -- a different task on the same
dataset family: whole-frame object detection (3-class:
marine_debris/gear_hardware/other_anthropogenic) rather than classification
of pre-cropped 96x96 target images (6-class: background/tire/chain/
propeller/can/bottle).

**Verified with real inference before any integration code was written**,
per the handoff's own instruction not to trust the metrics files alone:
loaded the checkpoint via `ultralytics.YOLO()` and ran `predict()` on all 5
real sample images in `YOLO_TrainedModel/sample_sonar_images/`. Got 7 real
detections across the 5 images, confidences 0.588-0.887, `model.names`
matching `YOLO_TrainedModel/model_contract.json` exactly
(`{0: marine_debris, 1: gear_hardware, 2: other_anthropogenic}`) --
structurally sound, not corrupted, not a static/hallucinated output. This
exact scenario is now permanent regression coverage:
`tests/test_yolo_debris_detector.py::test_predict_on_real_sample_images_finds_real_objects`.

**Real validated metrics** (`YOLO_TrainedModel/results.csv`, epoch 60/60,
cited here, not re-derived): **precision 0.961, recall 0.982, mAP50 0.983,
mAP50-95 0.801**, minimal cross-class confusion
(`YOLO_TrainedModel/confusion_matrix.png`).

**Side effect of installing ultralytics: torch moved 2.13.0 -> 2.14.0.**
`ultralytics` depends on `torch>=1.8.0`; the resolver picked 2.14.0+cpu on
install, upgrading the previously-pinned 2.13.0+cpu in place. Confirmed
still a CPU build, not the much larger CUDA one `requirements.txt`'s own
comment warns a plain `pip install -r requirements.txt` can pull. Re-pinned
`requirements.txt` to `torch==2.14.0` to match reality, and re-ran the full
E004 test suite against it (still passing) before committing that pin.

#### Decision 1: taxonomy -- extend `KNOWN_DEBRIS_SUBCLASSES`, don't remap

YOLO11s's 3 classes (`marine_debris`/`gear_hardware`/`other_anthropogenic`)
overlap neither `KNOWN_DEBRIS_SUBCLASSES`' existing fine-grained values
(`ghost_net`/`crab_pot`/`pipe`/`metal_debris`/`shipwreck`/`other_debris`)
nor the classical/quantum classifiers' trained vocabulary (`background`/
`tire`/`chain`/`propeller`/`can`/`bottle`). Three options were on the
table: (a) add the 3 new values to `KNOWN_DEBRIS_SUBCLASSES` as coarser
peers of the existing fine-grained ones, (b) lossily remap YOLO's classes
onto existing subclass values, (c) treat detection as a separate coarse
stage feeding into classification for fine-grained subclassing.

**Chose (a) -- which turns out to already be this codebase's existing
architecture, not a new idea.** `KNOWN_DEBRIS_SUBCLASSES` is explicitly
documented as "a vocabulary, not a constraint" (`app/models/enums.py`) --
new subclasses are meant to be added freely, and the mixed granularity
(fine-grained values from purpose-built detectors like E004's
"shipwreck", coarser values from a general detector like YOLO's
"gear_hardware") is honest: it reports exactly what each detector said,
at whatever granularity it actually operates at. (b) would have thrown
away real model signal to force a uniform-looking vocabulary -- exactly
the kind of fabrication this project avoids elsewhere (see the protection
logic below). (c) sounds different from (a) but isn't, in this codebase:
DETECTING already seeds a coarse `Target.debris_subclass` from the
detector's own `class_name` (`target_service._SUBCLASS_CLASS_NAMES`,
built for E004's "shipwreck" bootstrap), and CLASSIFYING already can
refine/confirm it. (a) is the concrete implementation of (c) using
machinery that already exists, rather than adding a second, redundant
orchestration stage.

**This also means zero new protection code was needed.**
`classification_service._detector_protected_class()` (built for E004,
see above) checks whether the classifier's *actual* trained vocabulary
includes the target's detector-seeded subclass -- not whether the
detector is E004 specifically. Since the classical classifier's real
vocabulary doesn't include `marine_debris`/`gear_hardware`/
`other_anthropogenic` either, the exact same guard protects YOLO's
output automatically. Verified live against a real, freshly-started
server (not just tests): processing a real ARIS debris image produced a
`marine_debris` target whose classical `ClassificationRecord.note` reads
*"NOT applied to target: classifier's trained vocabulary ['bottle', 'can',
'chain', 'natural_seabed', 'propeller', 'tire'] does not include
'marine_debris'..."* -- the identical protection message pattern E004 gets,
with zero E004-specific code touched. Regression coverage:
`tests/test_multi_model_detection.py::test_new_taxonomy_class_is_protected_from_a_classifier_that_never_saw_it`.

#### Decision 2: run alongside E004, not replacing it

E004 and YOLO11s answer different questions -- "is this specific blob a
shipwreck" (narrow specialist, segmentation-based) vs. "is there debris/
gear/anthropogenic material anywhere in this frame" (general-purpose,
detection-based) -- so replacing either with the other would be a real
capability loss with no justification. `Detection`'s own docstring
already anticipated this exact scenario: *"multiple detections (from
multiple models, or multiple runs of the same model) can and do point at
the same physical object; Target is where those get consolidated."*

`app/ml/model_registry.py` now has two independent, independently-gated
slots: `get_detection_model()` -- the **general-purpose** slot, repurposed
to gate on the YOLO11s checkpoint instead of E004's (falls back to
`FixtureThresholdDetector` exactly as before when absent) -- and the new
`get_shipwreck_detection_model()` -- the **specialist** slot, gated on
E004's checkpoint, returning `None` (not a fixture) when absent, since a
generic classical-CV stand-in specifically for "shipwreck detection"
wouldn't mean anything. `detection_service.run_detection()` runs the
general slot always, plus the specialist slot whenever it's registered,
merging both models' real detections into the survey's detection set --
each `Detection` row still records its own real `model_name`/
`model_version`, so nothing about provenance is lost by merging.

Verified live: processing a real ARIS debris image through a freshly
started server with both checkpoints registered produced
`"3 raw detection(s) from ['e004-unet-shipwreck-segmentation',
'yolo11s-marine-debris-fls']"` in the real job's `stage_log` -- 2 real
`marine_debris` detections from YOLO and 1 `shipwreck` detection from
E004 (a false positive on a non-shipwreck image, consistent with E004's
already-documented limitations above, not a new bug), all three carried
cleanly through classification, geolocation, GIS enrichment, risk
scoring, and priority without error. Regression coverage:
`tests/test_multi_model_detection.py::test_run_detection_merges_both_registered_models`,
plus `tests/test_e004_detector.py`'s updated registry tests (E004 now
asserted against `get_shipwreck_detection_model()`, not
`get_detection_model()`).

#### Decision 3: `requires_manual_review` -- a new field, deliberately not `uncertainty_service`

`YOLO_TrainedModel/model_contract.json` declares
`default_confidence_threshold: 0.5` and `manual_review_range: [0.25, 0.5]`
-- a raw detection-confidence policy from the model's own authors. This is
a genuinely different question from `uncertainty_service.compute_uncertainty()`,
which computes normalized entropy over a *classifier's* class
probabilities. One is "how sure was the detector this is something at
all"; the other is "how sure was the classifier which specific class it
is" -- conflating them would answer neither question correctly.

Added `requires_manual_review: bool | None` to both `Detection` and
`Target` (migration `0003_add_requires_manual_review`), computed once by
`YoloDebrisDetector.predict()` from the model's own declared thresholds
(`[0.25, 0.5)` confidence -> `True`) and copied onto `Target` at
target-creation time (`target_service.create_targets_from_detections`),
never recomputed afterward. **`None` means "this detector declares no
such policy"** (E004, `FixtureThresholdDetector`) -- **not** "reviewed and
cleared." Only YOLO's own detections ever get a real `True`/`False`.
Verified live: the same real end-to-end run above returned
`requires_manual_review: false` for both real YOLO `marine_debris`
targets (confidences 0.887/0.832, both above the review band) and
`requires_manual_review: null` for the E004 `shipwreck` target (E004
declares no such policy) -- in the same JSON response, both fields
reachable via `GET /surveys/{id}/report`. Regression coverage:
`tests/test_yolo_debris_detector.py::test_manual_review_boundary_is_a_pure_function`
(the `[0.25, 0.5)` boundary logic in isolation) and
`test_run_detection_merges_both_registered_models` (the live None-vs-bool
split across both models).

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

`app/api/v1/detections.py`, `targets.py`, `classification.py` -- no API
route file has changed across either real integration (E004 or YOLO11s).

In practice, both real integrations *did* need small, deliberate changes
beyond `model_registry.py` -- this section originally claimed otherwise,
which turned out to be optimistic rather than accurate. What actually
changed, and why it was a real requirement rather than scope creep:
`target_service.py` (seed `Target.debris_subclass` from the detector's own
`class_name`/copy `requires_manual_review` forward -- both are genuinely
new *data*, not new *behavior*, for existing code paths),
`classification_service.py` (the vocabulary-membership protection guard --
a real correctness fix, not a new model's fault), `detection_service.py`
(run more than one registered model and merge -- YOLO11s specifically
needed this, E004 alone did not), and one real Alembic migration
(`requires_manual_review` needed an actual new column; nothing before it
did). The stable claim is narrower than originally stated: the database
schema for `Detection`/`Target`'s *existing* fields doesn't change, and no
API route file does either -- not that zero services or migrations ever
will.
