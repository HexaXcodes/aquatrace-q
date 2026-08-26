"""Pydantic schema for EnvironmentContext (Phases 12-13)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import GISStatus


class EnvironmentContextRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_id: str

    reef_status: GISStatus
    reef_id: str | None = None
    reef_distance_m: float | None = None
    inside_reef: bool | None = None
    habitat_context: str | None = None

    mpa_status: GISStatus
    mpa_id: str | None = None
    mpa_name: str | None = None
    mpa_distance_m: float | None = None
    inside_mpa: bool | None = None
    protection_context: str | None = None

    created_at: datetime
    updated_at: datetime
