"""Feature extraction service (Phase 7)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.ml.feature_extractor import FeatureExtractor, StatisticalFeatureExtractor
from app.models.feature_vector import FeatureVector
from app.models.survey import Survey
from app.models.target import Target

logger = get_logger(__name__)

_DEFAULT_EXTRACTOR = StatisticalFeatureExtractor()


def extract_and_store_features(
    db: Session,
    target: Target,
    survey: Survey,
    extractor: FeatureExtractor | None = None,
) -> FeatureVector:
    extractor = extractor or _DEFAULT_EXTRACTOR
    extracted = extractor.extract(Path(survey.file_path), target.bbox)

    feature_vector = FeatureVector(
        target_id=target.id,
        feature_version=extracted.feature_version,
        dimensions=len(extracted.values),
        values=extracted.values,
        feature_names=extracted.names,
    )
    db.add(feature_vector)
    db.commit()
    db.refresh(feature_vector)

    logger.info(
        "feature_vector_created",
        extra={"target_id": target.id, "feature_version": feature_vector.feature_version},
    )
    return feature_vector


def get_latest_feature_vector(db: Session, target_id: str) -> FeatureVector | None:
    return db.execute(
        select(FeatureVector)
        .where(FeatureVector.target_id == target_id)
        .order_by(FeatureVector.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
