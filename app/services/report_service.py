"""
Report service (Phase 17).

Builds a per-target report row from whatever is actually in the
database for that target -- classification, environment, risk, and
priority are each independently `None`/status-flagged if that stage
never ran, rather than the report silently omitting the column or
inventing a value. Fully reproducible from DB state: calling this
twice against the same data returns byte-identical output.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.environment import EnvironmentContext
from app.models.priority import PriorityScore
from app.models.risk import RiskScore
from app.models.survey import Survey
from app.models.target import Target

_CSV_FIELDS = [
    "survey_id",
    "target_id",
    "classification",
    "debris_subclass",
    "confidence",
    "uncertainty",
    "requires_manual_review",
    "latitude",
    "longitude",
    "coordinate_source",
    "depth_m",
    "estimated_area_m2",
    "reef_status",
    "reef_distance_m",
    "inside_reef",
    "mpa_status",
    "mpa_distance_m",
    "inside_mpa",
    "risk_score",
    "risk_level",
    "priority_score",
    "priority_action",
    "recommended_method",
    "verification_required",
]


@dataclass(slots=True)
class ReportRow:
    survey_id: str
    target_id: str
    classification: str | None
    debris_subclass: str | None
    confidence: float | None
    uncertainty: float | None
    requires_manual_review: bool | None
    latitude: float | None
    longitude: float | None
    coordinate_source: str | None
    depth_m: float | None
    estimated_area_m2: float | None
    reef_status: str | None
    reef_distance_m: float | None
    inside_reef: bool | None
    mpa_status: str | None
    mpa_distance_m: float | None
    inside_mpa: bool | None
    risk_score: float | None
    risk_level: str | None
    priority_score: float | None
    priority_action: str | None
    recommended_method: str | None
    verification_required: bool | None

    def to_dict(self) -> dict:
        return {field_name: getattr(self, field_name) for field_name in _CSV_FIELDS}


@dataclass(slots=True)
class SurveyReport:
    survey_id: str
    survey_name: str
    generated_at: str
    target_count: int
    rows: list[ReportRow] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "survey_id": self.survey_id,
            "survey_name": self.survey_name,
            "generated_at": self.generated_at,
            "target_count": self.target_count,
            "targets": [row.to_dict() for row in self.rows],
        }

    def to_csv(self) -> str:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for row in self.rows:
            writer.writerow(row.to_dict())
        return buffer.getvalue()


def generate_survey_report(db: Session, survey: Survey) -> SurveyReport:
    targets = list(db.execute(select(Target).where(Target.survey_id == survey.id)).scalars().all())

    rows: list[ReportRow] = []
    for target in targets:
        environment = db.execute(
            select(EnvironmentContext).where(EnvironmentContext.target_id == target.id)
        ).scalar_one_or_none()
        risk = db.execute(select(RiskScore).where(RiskScore.target_id == target.id)).scalar_one_or_none()
        priority = db.execute(
            select(PriorityScore).where(PriorityScore.target_id == target.id)
        ).scalar_one_or_none()

        rows.append(
            ReportRow(
                survey_id=survey.id,
                target_id=target.id,
                classification=target.classification.value if target.classification else None,
                debris_subclass=target.debris_subclass,
                confidence=target.confidence,
                uncertainty=target.uncertainty,
                requires_manual_review=target.requires_manual_review,
                latitude=target.latitude,
                longitude=target.longitude,
                coordinate_source=target.coordinate_source.value if target.coordinate_source else None,
                depth_m=target.depth_m,
                estimated_area_m2=target.estimated_area_m2,
                reef_status=environment.reef_status.value if environment else None,
                reef_distance_m=environment.reef_distance_m if environment else None,
                inside_reef=environment.inside_reef if environment else None,
                mpa_status=environment.mpa_status.value if environment else None,
                mpa_distance_m=environment.mpa_distance_m if environment else None,
                inside_mpa=environment.inside_mpa if environment else None,
                risk_score=risk.score if risk else None,
                risk_level=risk.level.value if risk else None,
                priority_score=priority.score if priority else None,
                priority_action=priority.action.value if priority else None,
                recommended_method=priority.recommended_method.value if priority else None,
                verification_required=priority.verification_required if priority else None,
            )
        )

    return SurveyReport(
        survey_id=survey.id,
        survey_name=survey.name,
        generated_at=datetime.now(timezone.utc).isoformat(),
        target_count=len(rows),
        rows=rows,
    )
