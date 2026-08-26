"""Pydantic schemas for Mission/MissionTarget (Phase 16)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MissionStatus


class MissionCreate(BaseModel):
    start_latitude: float = Field(..., ge=-90, le=90)
    start_longitude: float = Field(..., ge=-180, le=180)
    vehicle_speed_mps: float | None = Field(default=None, gt=0)


class MissionTargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_id: str
    sequence: int
    distance_from_previous_m: float | None = None
    cumulative_distance_m: float | None = None


class MissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    survey_id: str
    status: MissionStatus
    start_latitude: float | None = None
    start_longitude: float | None = None
    total_distance_m: float | None = None
    estimated_duration_s: float | None = None
    vehicle_speed_mps: float | None = None
    targets: list[MissionTargetRead]
    created_at: datetime
    updated_at: datetime
