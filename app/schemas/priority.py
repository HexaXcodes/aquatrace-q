"""Pydantic schema for PriorityScore (Phase 15)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import PriorityAction, VerificationMethod


class PriorityScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_id: str
    score: float
    action: PriorityAction
    recommended_method: VerificationMethod
    verification_required: bool
    reasons: list[str]
    created_at: datetime
    updated_at: datetime
