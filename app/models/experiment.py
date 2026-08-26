"""Experiment ORM model (Phase 9 / 20).

Stores the result of one classical-vs-quantum classification
comparison run. Metrics are only ever what was actually measured on the
supplied dataset -- `classical_metrics`/`quantum_metrics` are NULL for
whichever side didn't genuinely run (see `ModelRunStatus`).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(64), nullable=False)
    sample_count: Mapped[int] = mapped_column(nullable=False)

    classical_status: Mapped[str] = mapped_column(String(16), nullable=False)
    classical_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    quantum_status: Mapped[str] = mapped_column(String(16), nullable=False)
    quantum_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Experiment id={self.id} n={self.sample_count}>"
