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
