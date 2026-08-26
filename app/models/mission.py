"""Mission + MissionTarget ORM models (Phase 16).

A Mission is a decision-support artifact: an ordered list of targets a
conservation team (or ROV/AUV operator) should visit, with distances
between consecutive stops. It does NOT drive any real vehicle -- see
`app/services/mission_service.py` for the explicit non-goal.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import MissionStatus


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    survey_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[MissionStatus] = mapped_column(
        Enum(MissionStatus, name="mission_status", native_enum=False, length=16),
        nullable=False,
        default=MissionStatus.DRAFT,
    )

    start_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    total_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    vehicle_speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    targets: Mapped[list["MissionTarget"]] = relationship(
        back_populates="mission", order_by="MissionTarget.sequence", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Mission id={self.id} status={self.status} stops={len(self.targets)}>"


class MissionTarget(Base):
    __tablename__ = "mission_targets"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    mission_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("targets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_from_previous_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    cumulative_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    mission: Mapped["Mission"] = relationship(back_populates="targets")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MissionTarget mission_id={self.mission_id} seq={self.sequence}>"
