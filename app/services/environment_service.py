"""Environment enrichment service (Phases 12-13)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.gis.registry import get_mpa_provider, get_reef_provider
from app.models.environment import EnvironmentContext
from app.models.target import Target

logger = get_logger(__name__)


def enrich_target_environment(db: Session, target: Target) -> EnvironmentContext | None:
    """
    Query the reef and MPA providers for `target`'s coordinates and
    persist the result. Returns `None` (and stores nothing) if the
    target has no coordinates yet -- that is a geolocation gap, not a
    GIS configuration gap, and callers should log it distinctly.
    """
    if target.latitude is None or target.longitude is None:
        return None

    reef_context = get_reef_provider().get_context(target.latitude, target.longitude)
    mpa_context = get_mpa_provider().get_context(target.latitude, target.longitude)

    existing = db.execute(
        select(EnvironmentContext).where(EnvironmentContext.target_id == target.id)
    ).scalar_one_or_none()

    row = existing or EnvironmentContext(target_id=target.id)
    row.reef_status = reef_context.status
    row.reef_id = reef_context.reef_id
    row.reef_distance_m = reef_context.distance_m
    row.inside_reef = reef_context.inside_reef
    row.habitat_context = reef_context.habitat_context

    row.mpa_status = mpa_context.status
    row.mpa_id = mpa_context.mpa_id
    row.mpa_name = mpa_context.mpa_name
    row.mpa_distance_m = mpa_context.distance_m
    row.inside_mpa = mpa_context.inside_mpa
    row.protection_context = mpa_context.protection_context

    db.add(row)
    db.commit()
    db.refresh(row)

    logger.info(
        "environment_enriched",
        extra={
            "target_id": target.id,
            "reef_status": reef_context.status.value,
            "mpa_status": mpa_context.status.value,
        },
    )
    return row


def get_environment_context(db: Session, target_id: str) -> EnvironmentContext | None:
    return db.execute(
        select(EnvironmentContext).where(EnvironmentContext.target_id == target_id)
    ).scalar_one_or_none()
