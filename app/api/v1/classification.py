"""Classification endpoint (Phase 20): GET /targets/{id}/classification"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.classification import ClassificationRecord
from app.schemas.classification import ClassificationRecordRead, TargetClassificationSummary
from app.services import target_service

router = APIRouter(tags=["classification"])


@router.get(
    "/targets/{target_id}/classification",
    response_model=TargetClassificationSummary,
    summary="Get a target's current classification summary and full run history",
)
def get_target_classification(target_id: str, db: Session = Depends(get_db)) -> TargetClassificationSummary:
    target = target_service.get_target(db, target_id)
    records = list(
        db.execute(
            select(ClassificationRecord)
            .where(ClassificationRecord.target_id == target_id)
            .order_by(ClassificationRecord.created_at.desc())
        )
        .scalars()
        .all()
    )
    return TargetClassificationSummary(
        target_id=target.id,
        classification=target.classification.value if target.classification else None,
        debris_subclass=target.debris_subclass,
        confidence=target.confidence,
        uncertainty=target.uncertainty,
        records=[ClassificationRecordRead.model_validate(r) for r in records],
    )
