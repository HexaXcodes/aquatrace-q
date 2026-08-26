"""Pydantic schemas for classification results (Phases 8-10)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ModelRunStatus, ModelStage


class ClassificationRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    target_id: str
    stage: ModelStage
    run_status: ModelRunStatus

    predicted_class: str | None = None
    probabilities: dict[str, float] | None = None
    confidence: float | None = None

    model_name: str
    model_version: str
    feature_version: str | None = None
    inference_time_ms: float | None = None
    note: str | None = None

    created_at: datetime


class TargetClassificationSummary(BaseModel):
    """Response for `GET /targets/{id}/classification`: current summary
    plus the full classical/quantum record history."""

    target_id: str
    classification: str | None = None
    debris_subclass: str | None = None
    confidence: float | None = None
    uncertainty: float | None = None
    records: list[ClassificationRecordRead]
