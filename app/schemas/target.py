"""Pydantic schemas for Target (Phase 6)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import CoordinateSource, TargetClass


class TargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    survey_id: str
    detection_id: str | None = None

    classification: TargetClass | None = None
    debris_subclass: str | None = None
    confidence: float | None = None
    uncertainty: float | None = None
    requires_manual_review: bool | None = None

    bbox: list[float] | None = None
    mask_path: str | None = None
    estimated_area_m2: float | None = None
    estimated_length_m: float | None = None
    estimated_width_m: float | None = None
    depth_m: float | None = None

    latitude: float | None = None
    longitude: float | None = None
    coordinate_source: CoordinateSource | None = None

    created_at: datetime
    updated_at: datetime


class TargetList(BaseModel):
    items: list[TargetRead]
    total: int
