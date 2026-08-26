"""FeatureVector ORM model (Phase 7).

Stores whatever feature representation the classifiers were run
against. `values` is a plain JSON array so the backend never has to
know the feature architecture (hand-engineered stats today, a PyTorch
CNN embedding tomorrow) -- only `dimensions` and `feature_version` need
to be internally consistent for a given classifier run.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class FeatureVector(Base):
    __tablename__ = "feature_vectors"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    target_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("targets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    feature_version: Mapped[str] = mapped_column(String(64), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    values: Mapped[list[float]] = mapped_column(JSON, nullable=False)

    # Free-form record of which extractors contributed which named
    # sub-features, e.g. {"intensity_mean": 0, "intensity_std": 1, ...}.
    # Optional -- only populated when the extractor tracks it.
    feature_names: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FeatureVector target_id={self.target_id} dims={self.dimensions}>"
