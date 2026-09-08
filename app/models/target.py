"""
Target ORM model (Phase 6).

A Target is the higher-level object every downstream stage (features,
classification, uncertainty, geolocation, GIS enrichment, risk,
priority, missions) reasons about. It is created from one (eventually
possibly several) `Detection` rows, and accumulates state as the
pipeline runs -- classification fields are populated in Phase 8/9,
`latitude`/`longitude` in Phase 11, and so on.

`classification` / `debris_subclass` mirror the winning classification
result once one exists; the full history of classification attempts
(classical AND quantum, every run) lives in `ClassificationRecord` and
is never overwritten.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import CoordinateSource, TargetClass


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    survey_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False, index=True
    )
    detection_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("detections.id", ondelete="SET NULL"), nullable=True
    )

    # --- Classification summary (Phase 8/9 write these; ClassificationRecord
    # keeps the full history) ------------------------------------------------
    classification: Mapped[TargetClass | None] = mapped_column(
        Enum(TargetClass, name="target_class", native_enum=False, length=32), nullable=True
    )
    debris_subclass: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    uncertainty: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Seeded once from the originating Detection at target-creation time
    # (see target_service.create_targets_from_detections) and never
    # touched again -- a detector-confidence-band fact, not something
    # classification/uncertainty stages recompute. NULL means the
    # originating detector declared no such policy; see Detection's own
    # field docstring for the None-vs-False distinction.
    requires_manual_review: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # --- Geometry ------------------------------------------------------------
    bbox: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    mask_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    estimated_area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_length_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_width_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    depth_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Geolocation (Phase 11) ------------------------------------------------
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    coordinate_source: Mapped[CoordinateSource | None] = mapped_column(
        Enum(CoordinateSource, name="coordinate_source", native_enum=False, length=32),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    detection: Mapped["Detection | None"] = relationship(back_populates="targets")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Target id={self.id} classification={self.classification}>"
