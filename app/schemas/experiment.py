"""Pydantic schemas for classification experiments (Phase 9/20)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExperimentSample(BaseModel):
    features: list[float]
    label: str


class ExperimentRequest(BaseModel):
    """A small labelled dataset to benchmark classical vs quantum on.

    This is deliberately caller-supplied rather than reading from a
    fixed table: until Shashank's real labelled sonar-feature dataset
    exists, callers (including the test suite) provide their own -- the
    experiment honestly reports on whatever it was given, never a
    canned "our model gets X% accuracy" number.
    """

    dataset_version: str
    feature_version: str
    samples: list[ExperimentSample] = Field(..., min_length=4)
    test_size: float = Field(default=0.3, gt=0, lt=1)


class ExperimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_version: str
    feature_version: str
    sample_count: int
    classical_status: str
    classical_metrics: dict | None = None
    quantum_status: str
    quantum_metrics: dict | None = None
    notes: str | None = None
    created_at: datetime
