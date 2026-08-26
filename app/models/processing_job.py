"""ProcessingJob ORM model (Phases 18-19).

Tracks one run of the full pipeline against a survey. `stage_log` is an
append-only list of `{stage, status, message, timestamp}` entries so
the *entire* run is reconstructable after the fact -- important both
for debugging and for the "no fake science" requirement: if QML or GIS
was skipped, that is a permanent, visible entry here, not something
inferred after the fact.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.enums import ProcessingJobStatus


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    survey_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    status: Mapped[ProcessingJobStatus] = mapped_column(
        Enum(ProcessingJobStatus, name="processing_job_status", native_enum=False, length=32),
        nullable=False,
        default=ProcessingJobStatus.QUEUED,
    )
    error_message: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # [{"stage": "DETECTING", "status": "OK", "message": "...", "at": "..."}]
    stage_log: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProcessingJob id={self.id} survey_id={self.survey_id} status={self.status}>"
