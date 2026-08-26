"""Pydantic schemas for ProcessingJob (Phases 18-19)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ProcessingJobStatus


class ProcessingRequest(BaseModel):
    """Optional AUV/ROV start position for mission planning at the end of
    the pipeline. If omitted, mission planning is skipped for this run
    (a mission can still be requested later via POST /surveys/{id}/missions)."""

    start_latitude: float | None = Field(default=None, ge=-90, le=90)
    start_longitude: float | None = Field(default=None, ge=-180, le=180)


class StageLogEntry(BaseModel):
    stage: str
    status: str
    message: str
    at: str


class ProcessingJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    survey_id: str
    status: ProcessingJobStatus
    error_message: str | None = None
    stage_log: list[StageLogEntry]
    created_at: datetime
    updated_at: datetime
