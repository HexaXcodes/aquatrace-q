"""
Survey ingestion service (Phase 5).

Owns the full lifecycle of a Survey record: creation, listing, lookup,
and the actual file-upload workflow (validate -> store -> parse ->
persist metadata -> flip status to UPLOADED).

This is intentionally the only place that knows about the on-disk
upload layout and the parser registry -- the API layer just calls
`upload_survey_file` and gets back an updated `Survey`.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    FileTooLargeError,
    InvalidSonarFileError,
    SurveyNotFoundError,
    UnsupportedSonarFormatError,
)
from app.core.logging import get_logger
from app.models.enums import SurveyStatus
from app.models.survey import Survey
from app.parsers import get_parser_for_extension
from app.schemas.survey import SurveyCreate, SurveyUploadMetadata
from app.utils.files import extension_of, resolve_within, sanitize_filename

logger = get_logger(__name__)


def create_survey(db: Session, payload: SurveyCreate) -> Survey:
    survey = Survey(name=payload.name, status=SurveyStatus.CREATED)
    db.add(survey)
    db.commit()
    db.refresh(survey)
    logger.info("survey_created", extra={"survey_id": survey.id, "survey_name": survey.name})
    return survey


def get_survey(db: Session, survey_id: str) -> Survey:
    survey = db.get(Survey, survey_id)
    if survey is None:
        raise SurveyNotFoundError(f"Survey '{survey_id}' does not exist.", survey_id=survey_id)
    return survey


def list_surveys(db: Session, limit: int = 50, offset: int = 0) -> tuple[list[Survey], int]:
    total = db.scalar(select(func.count()).select_from(Survey)) or 0
    items = (
        db.execute(
            select(Survey).order_by(Survey.created_at.desc()).limit(limit).offset(offset)
        )
        .scalars()
        .all()
    )
    return list(items), total


def _validate_upload(file: UploadFile, settings: Settings) -> str:
    if not file.filename:
        raise InvalidSonarFileError("Uploaded file has no filename.")

    extension = extension_of(file.filename)
    allowed = settings.allowed_sonar_extensions_tuple
    if extension not in allowed:
        raise UnsupportedSonarFormatError(
            f"Unsupported sonar file extension '.{extension}'. "
            f"Allowed: {', '.join(allowed)}.",
            extension=extension,
        )
    return extension


def upload_survey_file(
    db: Session,
    survey: Survey,
    file: UploadFile,
    metadata: SurveyUploadMetadata,
    settings: Settings | None = None,
) -> Survey:
    """
    Validate, persist to disk, parse, and attach an uploaded sonar file to
    an existing Survey record. Raises a domain exception (see
    `app.core.exceptions`) on any failure; the Survey row is left
    untouched (still CREATED) unless the whole flow succeeds.
    """
    settings = settings or get_settings()
    extension = _validate_upload(file, settings)

    survey_dir = resolve_within(settings.UPLOAD_DIRECTORY, survey.id)
    survey_dir.mkdir(parents=True, exist_ok=True)

    safe_name = sanitize_filename(file.filename)  # type: ignore[arg-type]
    destination = survey_dir / safe_name

    size_bytes = _stream_to_disk(file, destination, max_bytes=settings.MAX_UPLOAD_SIZE)
    logger.info(
        "survey_file_stored",
        extra={"survey_id": survey.id, "path": str(destination), "size_bytes": size_bytes},
    )

    try:
        parser = get_parser_for_extension(extension)
        parsed = parser.parse(destination)
    except InvalidSonarFileError:
        destination.unlink(missing_ok=True)
        raise
    except NotImplementedError as exc:
        destination.unlink(missing_ok=True)
        raise UnsupportedSonarFormatError(str(exc), extension=extension) from exc

    survey.file_path = str(destination)
    survey.file_type = extension
    survey.width = parsed.width
    survey.height = parsed.height

    # Explicit operator-supplied metadata always wins over whatever the
    # parser inferred (a parser for a richer format may fill some of
    # these in too; here it simply doesn't for images).
    for field_name in (
        "coordinate_reference_system",
        "origin_latitude",
        "origin_longitude",
        "meters_per_pixel",
        "depth_min",
        "depth_max",
        "sonar_frequency",
        "sensor_name",
    ):
        override = getattr(metadata, field_name)
        value = override if override is not None else getattr(parsed, field_name)
        setattr(survey, field_name, value)

    survey.status = SurveyStatus.UPLOADED
    survey.failure_reason = None

    db.add(survey)
    db.commit()
    db.refresh(survey)

    logger.info("survey_uploaded", extra={"survey_id": survey.id, "status": survey.status.value})
    return survey


def _stream_to_disk(file: UploadFile, destination: Path, max_bytes: int) -> int:
    """Copy `file` to `destination` in chunks, enforcing `max_bytes` as we
    go rather than after the fact (so we never buffer an oversized upload
    fully in memory or on disk before rejecting it)."""
    chunk_size = 1024 * 1024
    total = 0

    try:
        with destination.open("wb") as buffer:
            while chunk := file.file.read(chunk_size):
                total += len(chunk)
                if total > max_bytes:
                    raise FileTooLargeError(
                        f"Upload exceeds maximum size of {max_bytes} bytes.",
                        max_bytes=max_bytes,
                    )
                buffer.write(chunk)
    except FileTooLargeError:
        destination.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()

    return total
