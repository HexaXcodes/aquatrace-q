"""
Detection ORM model (Phase 6).

A Detection is the raw, unopinionated output of a single model run
against a single survey: "this model, at this confidence, thinks there
is something at this bounding box (and/or mask)". Nothing ecological or
geographic is attached here -- that reasoning happens on `Target`.

Multiple detections (from multiple models, or multiple runs of the same
model) can and do point at the same physical object; `Target` is where
those get consolidated.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    survey_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # [x1, y1, x2, y2] in pixel space. Nullable because a pure-segmentation
    # model may only produce a mask.
    bbox: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    mask_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Free-text on purpose (spec section 11): NATURAL_SEABED / ANTHROPOGENIC /
    # UNCERTAIN plus open-ended subclasses must be addable without a migration.
    class_name: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    inference_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    targets: Mapped[list["Target"]] = relationship(back_populates="detection")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Detection id={self.id} class={self.class_name} confidence={self.confidence}>"
