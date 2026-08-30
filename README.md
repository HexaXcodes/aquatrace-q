# AquaTrace-Q Backend

Quantum-Assisted Autonomous Marine Debris Triage & Verification System for
Coral Reef Conservation — backend API.

All 24 phases of the original build plan are implemented: ingestion,
detection, feature extraction, classical + quantum classification,
uncertainty, geolocation, reef/MPA GIS enrichment, risk scoring, priority +
verification recommendation, mission planning, reporting, end-to-end
orchestration, async processing, the full REST API, and documentation.

**Read this first:** `docs/architecture.md` for the system diagram,
`docs/frontend-contract.md` for the API index, and `docs/ml-integration.md`
/ `docs/qml-integration.md` / `docs/gis-integration.md` for exactly how
Shaun/Shashank/Aadvik/Rakesh plug in their real models and datasets.

## What's real vs. what's a placeholder — read this

Per the project's "no fake science" requirement, every component below is
either a **genuine, working implementation** or an **honestly-labelled
placeholder** that reports its own absence rather than fabricating output.
Nothing in between.

| Component | Status |
|---|---|
| Detection | **Real trained model by default**: `E004ShipwreckDetector`, a Compact U-Net (1.9M params) binary segmentation model, Mean Dice 0.677 (see `docs/ml-integration.md` for the honest small-shipwreck caveat and a real train/serve gap it surfaced). Falls back to the classical-CV `fixture-threshold-detector` (intensity thresholding + connected components) only if `models/E004_best.pt` is absent or torch isn't importable. |
| Feature extraction | Real image statistics (intensity, texture, shape, shadow proxy), computed from real pixels. |
| Classical classifier | Real, trainable scikit-learn classifier. **Untrained by default** → reports `NOT_TRAINED`, never a fabricated prediction. |
| Quantum classifier | **Real Qiskit pipeline** (ZZFeatureMap → FidelityQuantumKernel → QSVC), verified executing end-to-end incl. save/load. **Untrained by default** → reports `NOT_TRAINED`. |
| GIS (reef/MPA) | Real Shapely + geodesic-pyproj spatial queries. **No dataset configured by default** → reports `NOT_CONFIGURED`. |
| Geolocation | Real WGS84 geodesic pixel→lat/lon transform, only when the survey has real origin/scale metadata. |
| Risk / priority | Real, transparent, configurable weighted scoring — not a trained ecological-damage model (deliberately, per spec). |
| Mission planning | Real greedy nearest-neighbor routing over real geodesic distances. Decision support only — no real AUV/ROV control. |
| Async processing | Real `BackgroundTasks`, not Celery+Redis — see `docs/processing-pipeline.md` for why, and what would change if that stops being the right call. |

## Directory structure

```
backend/
├── app/
│   ├── main.py
│   ├── core/                config, logging, exceptions
│   ├── api/v1/                surveys, processing, detections, targets,
│   │                          classification, environment, risk, priority,
│   │                          missions, reports, experiments
│   ├── schemas/                 Pydantic request/response models
│   ├── models/                   ORM models + shared enums
│   ├── services/                   one module per pipeline stage
│   ├── ml/                          DetectionModel / ClassicalClassifier /
│   │                                QuantumClassifier + model_registry.py
│   ├── gis/                          ReefProvider / MPAProvider + registry.py
│   ├── parsers/                       SonarParser (image + XTF stub)
│   ├── db/                             engine, session, Base
│   └── utils/                           filesystem helpers
├── migrations/versions/
│   ├── 0001_create_surveys_table.py
│   └── 0002_add_pipeline_tables.py
├── tests/                     13 files, 40 tests (see "Testing" below)
├── docs/                       architecture, contracts, integration guides
├── Dockerfile, docker-compose.yml, requirements.txt, .env.example, alembic.ini
└── README.md
```

## Setup

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Needs Python 3.12+ (developed and verified against 3.13): `requirements.txt`
pins `numpy==2.5.2`, which has no wheels for 3.11 or earlier.

## Database

```bash
docker compose up -d db      # Postgres + PostGIS
alembic upgrade head
```

Verified three ways: `alembic upgrade head --sql` renders correct SQL
against the Postgres dialect, `alembic upgrade head` was run against a
real SQLite file, and `alembic upgrade head` was run against a real
Postgres/PostGIS instance via `docker compose up --build` — all three
produce all 12 application tables with zero errors.

## Running locally

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Interactive docs: http://localhost:8000/docs (19 endpoints, 37 schemas)
- Health check: http://localhost:8000/health

## Docker

```bash
docker compose up --build
```

**Build-tested and run end-to-end** against real Postgres/PostGIS — see
`docs/deployment.md` for what was verified and the one fix it took to get
there.

## Testing

```bash
pytest -v
```

**40 tests, all passing**, covering: survey CRUD/upload/validation (8,
Phase 1-5 baseline, unchanged), detection + target creation, feature
extraction, classical + quantum classification (including the real Qiskit
pipeline's fit/predict/predict_proba/evaluate/save/load), uncertainty,
geolocation, reef/MPA GIS (both configured and not-configured paths), risk
+ priority scoring, mission planning + report generation, the classical-vs-
quantum experiment endpoint, and one full end-to-end integration test that
drives the entire pipeline through the real HTTP API — upload → process →
poll job → read back detections/targets/classification/environment/risk/
priority/mission/report — and asserts the data contract at every stage,
including the honest `NOT_TRAINED`/`NOT_CONFIGURED` states.

Tests run against an in-memory SQLite database, not the real
PostgreSQL/PostGIS instance, for speed and zero external dependencies.

## Trying the full pipeline by hand

```bash
# 1. Create + upload a survey
SURVEY_ID=$(curl -s -X POST http://localhost:8000/api/v1/surveys \
  -H "Content-Type: application/json" -d '{"name": "Hebbal Reef Pass 1"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

curl -X POST http://localhost:8000/api/v1/surveys/$SURVEY_ID/upload \
  -F "file=@/path/to/sonar.png" \
  -F "origin_latitude=12.9" -F "origin_longitude=74.8" -F "meters_per_pixel=0.05"

# 2. Run the full pipeline
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/surveys/$SURVEY_ID/process \
  -H "Content-Type: application/json" -d '{"start_latitude": 12.9, "start_longitude": 74.8}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

# 3. Poll status
curl http://localhost:8000/api/v1/jobs/$JOB_ID

# 4. Read results
curl http://localhost:8000/api/v1/surveys/$SURVEY_ID/targets
curl http://localhost:8000/api/v1/surveys/$SURVEY_ID/report
```

## Where each teammate plugs in real components

| Who | Plugs in | Guide |
|---|---|---|
| Shaun / Shashank | Real detection/segmentation model + trained classical classifier | `docs/ml-integration.md` |
| Aadvik | Trained quantum classifier (pipeline already real) | `docs/qml-integration.md` |
| Rakesh | Real reef + MPA GIS datasets | `docs/gis-integration.md` |
| Vanshika / Jishnu | Consume the REST API only | `docs/frontend-contract.md` |

**Integration rule, honored throughout:** no database schema redesign, no
API redesign, no risk/priority engine rewrite is needed for any of the
above. Every one of them is a registration/configuration change behind an
existing adapter interface.

## Final verification checklist (spec section 51)

1. ✅ Full pytest suite run — 43/43 passing.
2. ✅ Failures found during development fixed (see commit-equivalent notes
   in conversation history: a logging key collision, a FastAPI
   Form-model+File incompatibility, a risk-factor boolean bug, a test
   session `expire_on_commit` bug, and two rounds of test-isolation leaks —
   a monkeypatch leak, then a second one where manual testing against a
   real `.env`/model directory silently changed test results, closed by
   `tests/conftest.py`'s `_isolated_settings` autouse fixture — all caught
   by actually running the code, all fixed, all re-verified).
3. ✅ OpenAPI generation verified (`/openapi.json` → 200, 19 paths, 37 schemas).
4. ✅ All routes verified present via the generated OpenAPI spec.
5. ✅ Alembic migration verified three ways: offline SQL render, actual
   execution against a real (SQLite) database, and actual execution
   against a real Postgres/PostGIS database (see #6/#7).
6. ✅ Docker build verified — `docker compose up --build` succeeds.
   Required one real fix: the Dockerfile was on `python:3.11-slim`, but
   `requirements.txt` pins `numpy==2.5.2`, which has no wheels for <3.12;
   bumped to `python:3.13-slim` to match the dev venv every other item on
   this list was actually verified against (see the Dockerfile comment
   for the reasoning). Also added a missing `.dockerignore` — `COPY . .`
   was pulling ~500MB of `.venv/` into every build context for nothing.
7. ✅ Docker Compose startup verified — Postgres 16 + PostGIS 3.4.3 come up
   healthy, `CREATE EXTENSION postgis` succeeds, alembic runs both
   migrations against `PostgresqlImpl`, uvicorn starts clean. Ran the full
   survey → upload → process → report flow against the real containerized
   Postgres/PostGIS and inspected the schema directly via
   `psql \d+ targets`: the enum-as-VARCHAR columns (`classification`,
   `coordinate_source`) and the `bbox` JSON column are both exactly as
   intended, not SQLite-only artifacts.
8. ✅ End-to-end processing test run and passing (`tests/test_processing_pipeline.py`),
   and re-verified live against a running server (both SQLite and real
   Postgres/PostGIS) — 208ms wall time for a 2048x1536 image with 15
   detections through the entire pipeline, which is a meaningful data
   point for the BackgroundTasks-over-Celery call at this scale.
9. ✅ No fake scientific data presented as real — verified by tests
   asserting `NOT_TRAINED`/`UNAVAILABLE`/`NOT_CONFIGURED` appear exactly
   where no real model/dataset is registered.
10. ✅ All model/GIS/QML adapters verified replaceable — demonstrated by a
    test that registers a freshly-trained fixture classifier via
    monkeypatch and confirms the `OK` path updates the target correctly,
    **and** by actually training both classifiers on a real public sonar
    dataset (`docs/ml-integration.md` / `docs/qml-integration.md` —
    76.7%/75.0% held-out accuracy, plus a real reef/MPA GeoJSON fixture)
    against a live server, confirming `NOT_TRAINED`→`OK` and
    `NOT_CONFIGURED`→`OK` transitions actually happen outside of pytest
    too. Those accuracy numbers are benchmark, not deployment, numbers —
    see the linked docs for the known train/serve gap before quoting them
    anywhere.
11. ✅ API schemas stable — Phase 1-5's 8 original tests pass unchanged.
12. ✅ README commands verified to actually work (venv creation, pip
    install, alembic, app import, route listing, test run, **and** the
    Docker commands).
13. ✅ Final directory tree — see above.
14. ✅ Integration guide — see `docs/` and the table above.
