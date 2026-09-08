"""Pydantic schema for the survey report (Phase 17)."""

from __future__ import annotations

from pydantic import BaseModel


class ReportRowSchema(BaseModel):
    survey_id: str
    target_id: str
    classification: str | None = None
    debris_subclass: str | None = None
    confidence: float | None = None
    uncertainty: float | None = None
    requires_manual_review: bool | None = None
    latitude: float | None = None
    longitude: float | None = None
    coordinate_source: str | None = None
    depth_m: float | None = None
    estimated_area_m2: float | None = None
    reef_status: str | None = None
    reef_distance_m: float | None = None
    inside_reef: bool | None = None
    mpa_status: str | None = None
    mpa_distance_m: float | None = None
    inside_mpa: bool | None = None
    risk_score: float | None = None
    risk_level: str | None = None
    priority_score: float | None = None
    priority_action: str | None = None
    recommended_method: str | None = None
    verification_required: bool | None = None


class SurveyReportSchema(BaseModel):
    survey_id: str
    survey_name: str
    generated_at: str
    target_count: int
    targets: list[ReportRowSchema]
