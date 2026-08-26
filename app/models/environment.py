"""
EnvironmentContext ORM model (Phases 12-13).

One row per target holding whatever the reef/MPA providers were able
to determine. `reef_status`/`mpa_status` are the honesty fields: when
no dataset is configured, `reef_status = NOT_CONFIGURED` and every reef
numeric field stays NULL rather than silently defaulting to "far from
any reef".
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.enums import GISStatus


class EnvironmentContext(Base):
    __tablename__ = "environment_contexts"

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

    # --- Reef context ----------------------------------------------------------
    reef_status: Mapped[GISStatus] = mapped_column(
        Enum(GISStatus, name="reef_status", native_enum=False, length=32), nullable=False
    )
    reef_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reef_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    inside_reef: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    habitat_context: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # --- MPA context -------------------------------------------------------------
    mpa_status: Mapped[GISStatus] = mapped_column(
        Enum(GISStatus, name="mpa_status", native_enum=False, length=32), nullable=False
    )
    mpa_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mpa_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    mpa_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    inside_mpa: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    protection_context: Mapped[str | None] = mapped_column(String(256), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EnvironmentContext target_id={self.target_id} reef={self.reef_status} mpa={self.mpa_status}>"
