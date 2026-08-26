# Processing Pipeline (Phase 18)

`app/services/processing_service.py::run_pipeline()` runs every stage below
against one survey, recording each stage's outcome on the `ProcessingJob`
row's `stage_log`. Triggered via `POST /api/v1/surveys/{id}/process`, which
returns immediately (`202`) with a job id; poll `GET /api/v1/jobs/{id}`.

| Stage | What it does | If the optional input is missing |
|---|---|---|
| `VALIDATING` | Confirms the survey has an uploaded file | **Hard failure** → job `FAILED` |
| `PREPROCESSING` | Currently a pass-through (no preprocessing pipeline built yet — logged honestly, not silently skipped) | n/a |
| `DETECTING` | Runs the registered `DetectionModel`, creates `Detection` + `Target` rows | Zero detections is a valid, logged outcome |
| `CLASSIFYING` | Extracts features, runs the classical classifier | Untrained classifier → per-target `run_status=NOT_TRAINED`, pipeline continues |
| `QML_CLASSIFYING` | Runs the quantum classifier | Untrained/unavailable → `NOT_TRAINED`/`UNAVAILABLE`, pipeline continues |
| `GEOLOCATING` | Pixel → lat/lon via survey origin + meters_per_pixel | Missing metadata → target stays ungeolocated, logged |
| `GIS_ENRICHMENT` | Reef + MPA context for geolocated targets | No dataset configured → `NOT_CONFIGURED`, pipeline continues |
| `RISK_SCORING` | Transparent weighted risk score | Missing factors just contribute 0 |
| `PRIORITIZING` | Verification priority + recommended method | — |
| `MISSION_PLANNING` | Ranked visit order, if a start coordinate was supplied | No start coordinate → stage marked `SKIPPED`, not failed |
| `REPORTING` | Confirms the report can be generated from DB state | — |
| `COMPLETED` | Terminal success state | |
| `FAILED` | Terminal failure state, with `error_message` | |

## Failure semantics

A stage that hits a genuinely optional/unavailable component (untrained
model, unconfigured GIS, ungeolocatable target) **never** fails the job —
it's recorded as an honest note and the pipeline moves on, so the rest of
the survey still gets fully processed. Only a true blocker (no uploaded
file; an unhandled exception) fails the job, and even then the failure is
recorded on the job row rather than raised to the caller of `/process`
(which has already received its `202`).

## Async processing (Phase 19)

Runs via FastAPI `BackgroundTasks`, not Celery+Redis — see the docstring in
`app/api/v1/processing.py` for the explicit reasoning (pipeline runtime is
low single-digit seconds at this scale; a broker/worker pool buys nothing
yet and couldn't be exercised in this sandbox anyway). The background task
uses `app.db.session.get_session_factory()` rather than importing the
production session directly, specifically so it can be swapped for a
per-test in-memory database — see `tests/test_processing_pipeline.py` for
the full pipeline running via the real API, backend included.
