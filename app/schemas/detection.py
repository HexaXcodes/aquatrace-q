"""Pydantic schemas for Detection (Phase 6)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DetectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    survey_id: str
    bbox: list[float] | None = None
    mask_path: str | None = None
    class_name: str
    confidence: float
    requires_manual_review: bool | None = None
    model_name: str
    model_version: str
    inference_time_ms: float | None = None
    created_at: datetime


class DetectionList(BaseModel):
    items: list[DetectionRead]
    total: int
