"""
Survey ORM model.

A Survey is one side-scan sonar acquisition (a single towfish/AUV pass,
or a single uploaded image standing in for one during development).
Every Detection, Target, and Mission in later phases hangs off a
Survey via `survey_id`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.enums import SurveyStatus


class Survey(Base):
    __tablename__ = "surveys"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- File info, populated once the file is uploaded -------------------
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Sonar / navigation metadata ---------------------------------------
    # All nullable: real values are only ever set when genuinely supplied
    # (either in sonar-native metadata or explicitly by the uploader) --
    # never fabricated. See spec section 8 & 19.
    coordinate_reference_system: Mapped[str | None] = mapped_column(String(64), nullable=True)
    origin_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    origin_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    meters_per_pixel: Mapped[float | None] = mapped_column(Float, nullable=True)
    depth_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    depth_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    sonar_frequency: Mapped[float | None] = mapped_column(Float, nullable=True)
    sensor_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    status: Mapped[SurveyStatus] = mapped_column(
        Enum(SurveyStatus, name="survey_status", native_enum=False, length=32),
        nullable=False,
        default=SurveyStatus.CREATED,
    )
    failure_reason: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<Survey id={self.id} name={self.name!r} status={self.status}>"
