"""RiskScore ORM model (Phase 14).

Stores the transparent, weighted risk score for a target along with
the individual factor contributions, so the frontend/judges can see
*why* a score is what it is rather than trusting a black box.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.enums import RiskLevel


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    target_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("targets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    score: Mapped[float] = mapped_column(Float, nullable=False)  # 0-100
    level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, name="risk_level", native_enum=False, length=16), nullable=False
    )

    # [{"name": "debris_type", "contribution": 30}, ...]
    factors: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    weights_version: Mapped[str] = mapped_column(String(32), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RiskScore target_id={self.target_id} score={self.score} level={self.level}>"
