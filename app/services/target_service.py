"""Target service (Phase 6)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import TargetNotFoundError
from app.core.logging import get_logger
from app.models.detection import Detection
from app.models.enums import TargetClass
from app.models.target import Target

logger = get_logger(__name__)

# Coarse detector output -> TargetClass. Anything not in this map becomes
# UNCERTAIN rather than silently dropped -- see spec section 11 ("do not
# hardcode the database around only these classes").
_CLASS_NAME_MAP: dict[str, TargetClass] = {
    "NATURAL_SEABED": TargetClass.NATURAL_SEABED,
    "ANTHROPOGENIC": TargetClass.ANTHROPOGENIC,
    "UNCERTAIN": TargetClass.UNCERTAIN,
}


def create_targets_from_detections(db: Session, detections: list[Detection]) -> list[Target]:
    """
    Create one Target per Detection that isn't confidently natural
    seabed. This is a 1:1 mapping for now (Phase 6); a later phase may
    introduce N:1 clustering of detections that overlap spatially into a
    single target, which only changes this function.
    """
    targets: list[Target] = []
    for detection in detections:
        coarse_class = _CLASS_NAME_MAP.get(detection.class_name, TargetClass.UNCERTAIN)
        if coarse_class is TargetClass.NATURAL_SEABED:
            continue  # not worth tracking as a triage target

        target = Target(
            survey_id=detection.survey_id,
            detection_id=detection.id,
            classification=coarse_class,
            confidence=detection.confidence,
            bbox=detection.bbox,
            mask_path=detection.mask_path,
        )
        db.add(target)
        targets.append(target)

    db.commit()
    for target in targets:
        db.refresh(target)

    logger.info("targets_created", extra={"count": len(targets)})
    return targets


def get_target(db: Session, target_id: str) -> Target:
    target = db.get(Target, target_id)
    if target is None:
        raise TargetNotFoundError(f"Target '{target_id}' does not exist.", target_id=target_id)
    return target


def list_targets(db: Session, survey_id: str) -> list[Target]:
    return list(
        db.execute(select(Target).where(Target.survey_id == survey_id).order_by(Target.created_at))
        .scalars()
        .all()
    )
