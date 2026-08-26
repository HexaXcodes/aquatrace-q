# Database

PostgreSQL + PostGIS (production/dev via Docker Compose); tests use an
in-memory SQLite database (see `tests/conftest.py`) — every model column
type used is compatible with both (enums are stored as plain `VARCHAR` with
`native_enum=False`, specifically so SQLite can run the same schema without
a separate test-only migration path).

## Tables

| Table | Purpose | Key relationships |
|---|---|---|
| `surveys` | One sonar acquisition | — |
| `detections` | Raw per-model output | → `surveys` |
| `targets` | Consolidated triage object | → `surveys`, → `detections` |
| `feature_vectors` | Extracted features per target, versioned | → `targets` |
| `classification_records` | Full history of every classical/quantum run | → `targets`, → `feature_vectors` |
| `environment_contexts` | Reef/MPA context, one row per target | → `targets` (unique) |
| `risk_scores` | Explainable risk score + factor breakdown | → `targets` (unique) |
| `priority_scores` | Verification priority + recommended method | → `targets` (unique) |
| `missions` / `mission_targets` | Ranked visit plans | → `surveys`, → `targets` |
| `processing_jobs` | One row per pipeline run, with a full stage log | references `survey_id` (no FK — a job can outlive stricter survey lifecycle changes) |
| `experiments` | Classical-vs-quantum comparison runs | — |

## Migrations

- `0001_create_surveys_table.py` — Phase 1-5 baseline (also enables the
  `postgis` extension up front, for later phases).
- `0002_add_pipeline_tables.py` — every table above.

Run with `alembic upgrade head`. Verified in this environment two ways:
`alembic upgrade head --sql` (offline SQL rendering against the Postgres
dialect) and an actual `alembic upgrade head` against a real SQLite file
(Postgres itself isn't available in the sandbox this was built in) — both
produce all 12 application tables + `alembic_version` with no errors.

## Why some fields are enums-as-strings

`native_enum=False` (see every `Enum(...)` column) creates a plain
`VARCHAR` with a `CHECK` constraint on Postgres, rather than a native
Postgres `ENUM` type. This avoids a whole category of migration pain
(native enums require a dedicated `ALTER TYPE ... ADD VALUE` migration any
time a new status value is added — e.g. `ProcessingJobStatus` gained
several values across this project's phases) at negligible cost.
