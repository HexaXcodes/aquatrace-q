"""Pydantic schema for RiskScore (Phase 14)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import RiskLevel


class RiskFactorRead(BaseModel):
    name: str
    contribution: float
    detail: str


class RiskScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_id: str
    score: float
    level: RiskLevel
    factors: list[dict]
    weights_version: str
    created_at: datetime
    updated_at: datetime
