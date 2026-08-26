# Frontend Contract

Everything here is generated live at `/docs` (Swagger UI) and
`/openapi.json` — this file is a narrative index, not the source of truth.
If this document and `/docs` ever disagree, `/docs` is correct.

The frontend should never need to know: SQLAlchemy, PostGIS, Qiskit, or any
model file format. Every field below is a plain JSON value.

## Survey lifecycle

| Step | Endpoint | Notes |
|---|---|---|
| Create | `POST /api/v1/surveys` | `{"name": "..."}` → `SurveyRead`, `status: CREATED` |
| Upload | `POST /api/v1/surveys/{id}/upload` | multipart file + optional metadata form fields → `status: UPLOADED` |
| Get | `GET /api/v1/surveys/{id}` | |
| List | `GET /api/v1/surveys` | paginated (`limit`, `offset`) |
| Process | `POST /api/v1/surveys/{id}/process` | `{"start_latitude": ..., "start_longitude": ...}` (both optional) → `202` + `ProcessingJobRead` |
| Job status | `GET /api/v1/jobs/{id}` | poll until `status == "COMPLETED"` or `"FAILED"` |

## Per-survey resources (after processing)

| Resource | Endpoint |
|---|---|
| Detections (raw model output) | `GET /api/v1/surveys/{id}/detections` |
| Targets | `GET /api/v1/surveys/{id}/targets` |
| Report (JSON) | `GET /api/v1/surveys/{id}/report` |
| Report (CSV) | `GET /api/v1/surveys/{id}/report.csv` |

## Per-target resources

| Resource | Endpoint |
|---|---|
| Detail | `GET /api/v1/targets/{id}` |
| Classification (summary + full history) | `GET /api/v1/targets/{id}/classification` |
| Environment (reef/MPA) | `GET /api/v1/targets/{id}/environment` |
| Risk | `GET /api/v1/targets/{id}/risk` |
| Priority | `GET /api/v1/targets/{id}/priority` |

## Missions

| Step | Endpoint |
|---|---|
| Build | `POST /api/v1/surveys/{id}/missions` → `{"start_latitude", "start_longitude", "vehicle_speed_mps"?}` |
| Get | `GET /api/v1/missions/{id}` |

## Experiments (classical vs quantum)

| Step | Endpoint |
|---|---|
| Run | `POST /api/v1/experiments/classification` |
| Get | `GET /api/v1/experiments/{id}` |

## Fields the frontend must render honestly, not paper over

These "status" fields are not edge cases — they are core to the product's
honesty guarantee, and every screen that shows the field next to it should
handle all their values, not just the "happy path" one:

- `ClassificationRecordRead.run_status`: `OK` | `NOT_TRAINED` | `UNAVAILABLE` | `TEST_FIXTURE`
  — when not `OK`/`TEST_FIXTURE`, `predicted_class`/`probabilities` are `null`.
  Render "not yet classified" / "quantum unavailable", not a blank confidence bar.
- `EnvironmentContextRead.reef_status` / `.mpa_status`: `OK` | `NOT_CONFIGURED` | `TEST_FIXTURE`
  — `NOT_CONFIGURED` means "no reef/MPA dataset loaded", not "far from any reef".
- `TargetRead.coordinate_source`: `GPS` | `SONAR_METADATA` | `SURVEY_TRANSFORM` | `SIMULATED` | `null`
  — `null` means the target has no coordinates at all yet.
- `ProcessingJobRead.status` / `.stage_log`: the full stage-by-stage history,
  including any stage that reported "SKIPPED" (e.g. mission planning with no
  start coordinate supplied).
