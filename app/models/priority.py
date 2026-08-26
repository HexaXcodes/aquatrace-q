"""PriorityScore ORM model (Phase 15).

Distinct from RiskScore: risk answers "how ecologically/operationally
dangerous is this debris", priority answers "what should the
conservation team actually go do about it right now" -- which also
factors in classification uncertainty and confidence, not just risk.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.enums import PriorityAction, VerificationMethod


class PriorityScore(Base):
    __tablename__ = "priority_scores"

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
    action: Mapped[PriorityAction] = mapped_column(
        Enum(PriorityAction, name="priority_action", native_enum=False, length=16),
        nullable=False,
    )
    recommended_method: Mapped[VerificationMethod] = mapped_column(
        Enum(VerificationMethod, name="verification_method", native_enum=False, length=16),
        nullable=False,
    )
    verification_required: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Human-readable reasons, e.g. ["risk=CRITICAL", "uncertainty=HIGH"].
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PriorityScore target_id={self.target_id} action={self.action}>"
