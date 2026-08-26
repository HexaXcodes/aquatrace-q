# Deployment

## Local (no Docker)

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# point DATABASE_URL at a running Postgres/PostGIS instance, then:
alembic upgrade head
uvicorn app.main:app --reload
```

Needs Python 3.12+ (developed and verified against 3.13): `requirements.txt`
pins `numpy==2.5.2`, which has no wheels for 3.11 or earlier.

## Docker Compose (backend + Postgres/PostGIS)

```bash
docker compose up --build
```

`docker-compose.yml` runs `alembic upgrade head` automatically before
starting uvicorn (see the `backend` service's `command`). Volumes are
mounted for `uploads/`, `data/`, `outputs/`, and `models/` so uploaded
sonar files and any trained model artifacts (`classical_classifier.joblib`,
`quantum_classifier.pkl`) survive container restarts.

No Redis/Celery service is included — see `docs/processing-pipeline.md`
("Async processing") for why `BackgroundTasks` is the right choice at this
project's current scale, and what would need to change if that stops being
true.

**Verification status:** build-tested and run end-to-end. `docker compose
up --build` succeeds; Postgres 16 + PostGIS 3.4.3 come up healthy,
`CREATE EXTENSION postgis` succeeds, alembic runs both migrations against
the real database (`Context impl PostgresqlImpl`, not SQLite), and
uvicorn starts clean. The full survey → upload → process → report flow
was run against the containerized Postgres/PostGIS backend and the
resulting schema inspected directly via `psql \d+ targets` — the
enum-as-VARCHAR columns and the `bbox` JSON column are exactly as
intended.

Getting there required one real fix: the Dockerfile was pinned to
`python:3.11-slim`, but `requirements.txt`'s `numpy==2.5.2` has no wheels
for <3.12, so the build failed immediately on a fresh image. Bumped to
`python:3.13-slim` to match the dev environment everything else in this
repo has been verified against, rather than downgrading the numpy pin (see
the Dockerfile's own comment for the full reasoning). Also added a missing
`.dockerignore` — without one, `COPY . .` was pulling the ~500MB local
`.venv/` into every build context.

## Environment variables

See `.env.example` for the full list. Everything has a safe default except
`DATABASE_URL`, which must point at a real Postgres/PostGIS instance in any
non-Docker-Compose deployment.

Notable settings introduced in Phases 6-20 (all in `app/core/config.py`):

| Variable | Purpose |
|---|---|
| `QML_ENABLED`, `QML_FEATURE_DIMENSIONS` | Toggle/tune the quantum classifier |
| `REEF_DATA_PATH`, `MPA_DATA_PATH`, `GIS_ENABLED` | Point at real GIS datasets (see `docs/gis-integration.md`) |
| `RISK_WEIGHT_*`, `RISK_LEVEL_*_THRESHOLD` | Tune the risk engine without a code change |
| `PRIORITY_*_THRESHOLD` | Tune the priority engine |
| `UNCERTAINTY_*_THRESHOLD` | Tune uncertainty level bands |
| `MISSION_DEFAULT_VEHICLE_SPEED_MPS` | Default AUV/ROV speed for mission duration estimates |

## Health check

`GET /health` returns `{"status": "ok", "service": ..., "version": ...}` —
use this as the container/load-balancer health check target.
