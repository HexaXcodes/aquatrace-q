"""
ClassificationRecord ORM model (Phases 8-9).

Every classifier invocation against a target -- classical or quantum --
is stored here, in full, forever. `Target.classification/confidence`
holds only the current "winning" summary; this table is the audit
trail and is what `experiment_service` compares classical vs quantum
against.

`run_status` is the honesty mechanism required by spec section 8/9/49:
a row with `run_status = NOT_TRAINED` or `UNAVAILABLE` has
`predicted_class/probabilities = NULL` -- it is never populated with a
fabricated prediction just so the row "looks complete".
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.enums import ModelRunStatus, ModelStage


class ClassificationRecord(Base):
    __tablename__ = "classification_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    target_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("targets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_vector_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("feature_vectors.id", ondelete="SET NULL"), nullable=True
    )

    stage: Mapped[ModelStage] = mapped_column(
        Enum(ModelStage, name="model_stage", native_enum=False, length=16), nullable=False
    )
    run_status: Mapped[ModelRunStatus] = mapped_column(
        Enum(ModelRunStatus, name="model_run_status", native_enum=False, length=16),
        nullable=False,
    )

    predicted_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # {"ghost_net": 0.52, "natural_seabed": 0.43, ...} -- only present when
    # run_status == OK or TEST_FIXTURE.
    probabilities: Mapped[dict[str, float] | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    inference_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Free-text explanation for NOT_TRAINED/UNAVAILABLE rows, e.g.
    # "No trained QuantumClassifier registered for model_version=v1".
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ClassificationRecord target_id={self.target_id} stage={self.stage} status={self.run_status}>"
