"""
Reprocessing (re-running POST /surveys/{id}/process on an already-
processed survey) replaces the prior detection/target batch instead of
accumulating a second, duplicate set alongside it.

Regression coverage for a real bug: reprocessing a survey without this
fix doubled every downstream count -- detections, targets, feature
vectors, classification records, risk scores, priority scores, and the
survey report's own target_count -- confirmed live against a real
running server before this fix existed. See
target_service.delete_targets_for_survey()'s docstring for the full
reasoning (replace, not accumulate; relies on real FK cascade, which
required turning on `PRAGMA foreign_keys=ON` for SQLite -- see
app/db/database.py -- since SQLite silently ignores `ondelete=CASCADE`
otherwise, unlike Postgres).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import create_uploaded_survey


def _process(client: TestClient, survey_id: str) -> dict:
    response = client.post(f"/api/v1/surveys/{survey_id}/process", json={})
    assert response.status_code == 202
    job = client.get(f"/api/v1/jobs/{response.json()['id']}").json()
    assert job["status"] == "COMPLETED", job.get("error_message") or job["stage_log"]
    return job


def test_reprocessing_replaces_rather_than_doubles(client: TestClient) -> None:
    survey = create_uploaded_survey(client, "Reprocess Replace Survey")
    survey_id = survey["id"]

    _process(client, survey_id)
    detections_after_first = client.get(f"/api/v1/surveys/{survey_id}/detections").json()
    targets_after_first = client.get(f"/api/v1/surveys/{survey_id}/targets").json()
    first_detection_count = detections_after_first["total"]
    first_target_count = targets_after_first["total"]
    assert first_detection_count > 0  # the synthetic fixture image has real blobs to find
    assert first_target_count > 0

    second_job = _process(client, survey_id)
    detections_after_second = client.get(f"/api/v1/surveys/{survey_id}/detections").json()
    targets_after_second = client.get(f"/api/v1/surveys/{survey_id}/targets").json()

    # The bug this regression-tests: these used to be 2x the first-run
    # counts (identical rows duplicated), not equal to them.
    assert detections_after_second["total"] == first_detection_count
    assert targets_after_second["total"] == first_target_count

    # The old target/detection ids are genuinely gone, not just
    # coincidentally equal in count to a leftover-plus-new mix.
    first_target_ids = {t["id"] for t in targets_after_first["items"]}
    second_target_ids = {t["id"] for t in targets_after_second["items"]}
    assert first_target_ids.isdisjoint(second_target_ids)

    # The pipeline log says so explicitly, not silently.
    stage_messages = " ".join(entry["message"] for entry in second_job["stage_log"])
    assert "cleared" in stage_messages.lower()
    assert f"{first_detection_count} prior detection" in stage_messages
    assert f"{first_target_count} prior target" in stage_messages


def test_reprocessing_does_not_double_the_survey_report_or_risk_priority_rows(client: TestClient) -> None:
    survey = create_uploaded_survey(client, "Reprocess Report Survey")
    survey_id = survey["id"]

    _process(client, survey_id)
    report_after_first = client.get(f"/api/v1/surveys/{survey_id}/report").json()
    first_target_count = report_after_first["target_count"]
    assert first_target_count > 0

    _process(client, survey_id)
    report_after_second = client.get(f"/api/v1/surveys/{survey_id}/report").json()

    # This is the actual user-facing symptom: a conservation team
    # re-running a survey (e.g. after a new model lands) must not see
    # double the real number of debris targets in their report.
    assert report_after_second["target_count"] == first_target_count
    assert len(report_after_second["targets"]) == first_target_count


def test_delete_targets_for_survey_cascades_to_real_child_rows(client: TestClient) -> None:
    """Proves the bulk delete's reliance on real ON DELETE CASCADE (not a
    manual per-table delete) actually removes every child row, in SQLite
    too -- this only holds because app/db/database.py turns on
    `PRAGMA foreign_keys=ON` for SQLite connections; without it this
    delete would silently leave orphaned feature_vectors/
    classification_records/risk_scores/priority_scores/environment_contexts
    behind (it would still work correctly against real Postgres, which
    enforces FKs by default -- the gap was dev/test-only, but still a
    real gap)."""
    from sqlalchemy import text

    from app.db.session import get_session_factory
    from app.services import target_service

    survey = create_uploaded_survey(client, "Cascade Delete Survey")
    survey_id = survey["id"]
    _process(client, survey_id)

    db = get_session_factory()()
    try:
        target_ids = [row[0] for row in db.execute(text("SELECT id FROM targets WHERE survey_id = :sid"), {"sid": survey_id})]
        assert target_ids  # the fixture detector found real targets to work with

        deleted_count = target_service.delete_targets_for_survey(db, survey_id)
        assert deleted_count == len(target_ids)

        for table in ("feature_vectors", "classification_records", "environment_contexts", "risk_scores", "priority_scores"):
            placeholders = ",".join(f"'{tid}'" for tid in target_ids)
            remaining = db.execute(text(f"SELECT COUNT(*) FROM {table} WHERE target_id IN ({placeholders})")).scalar()
            assert remaining == 0, f"{table} left {remaining} orphaned row(s) after cascade delete"
    finally:
        db.close()
