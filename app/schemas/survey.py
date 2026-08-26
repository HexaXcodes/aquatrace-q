"""
Pydantic v2 schemas for the Survey resource.

These are the exact shapes the frontend receives from
`/api/v1/surveys*`. Anything added to `SurveyRead` becomes part of the
frontend contract (see `docs/frontend-contract.md`), so fields are only
added here once they're genuinely populated by the backend.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SurveyStatus


class SurveyCreate(BaseModel):
    """Payload for `POST /api/v1/surveys` -- creates an empty survey record
    that a file is attached to in a second step."""

    name: str = Field(..., min_length=1, max_length=255, examples=["Hebbal Reef Pass 1"])


class SurveyUploadMetadata(BaseModel):
    """
    Optional form-field overrides accepted alongside the uploaded file.

    None of these are ever inferred from a plain PNG/JPEG -- see spec
    section 7 ("Do NOT pretend PNG contains sonar metadata"). If the
    survey operator has this information from the acquisition log, it's
    supplied explicitly here; otherwise the fields stay NULL.
    """

    coordinate_reference_system: str | None = Field(default=None, examples=["EPSG:4326"])
    origin_latitude: float | None = Field(default=None, ge=-90, le=90)
    origin_longitude: float | None = Field(default=None, ge=-180, le=180)
    meters_per_pixel: float | None = Field(default=None, gt=0)
    depth_min: float | None = Field(default=None)
    depth_max: float | None = Field(default=None)
    sonar_frequency: float | None = Field(default=None, gt=0, description="MHz")
    sensor_name: str | None = Field(default=None, max_length=128)


class SurveyRead(BaseModel):
    """Full survey representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str

    file_path: str | None = None
    file_type: str | None = None
    width: int | None = None
    height: int | None = None

    coordinate_reference_system: str | None = None
    origin_latitude: float | None = None
    origin_longitude: float | None = None
    meters_per_pixel: float | None = None
    depth_min: float | None = None
    depth_max: float | None = None
    sonar_frequency: float | None = None
    sensor_name: str | None = None

    status: SurveyStatus
    failure_reason: str | None = None

    created_at: datetime
    updated_at: datetime


class SurveyList(BaseModel):
    """Paginated list wrapper for `GET /api/v1/surveys`."""

    items: list[SurveyRead]
    total: int
    limit: int
    offset: int
