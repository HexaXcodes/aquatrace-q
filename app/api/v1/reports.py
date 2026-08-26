"""Report endpoints (Phase 20): GET /surveys/{id}/report[.csv]"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.report import SurveyReportSchema
from app.services import report_service, survey_service

router = APIRouter(tags=["reports"])


@router.get(
    "/surveys/{survey_id}/report",
    response_model=SurveyReportSchema,
    summary="Get the full survey report as JSON",
)
def get_survey_report_json(survey_id: str, db: Session = Depends(get_db)) -> SurveyReportSchema:
    survey = survey_service.get_survey(db, survey_id)
    report = report_service.generate_survey_report(db, survey)
    return SurveyReportSchema(**report.to_dict())


@router.get(
    "/surveys/{survey_id}/report.csv",
    response_class=PlainTextResponse,
    summary="Get the full survey report as CSV",
)
def get_survey_report_csv(survey_id: str, db: Session = Depends(get_db)) -> str:
    survey = survey_service.get_survey(db, survey_id)
    report = report_service.generate_survey_report(db, survey)
    return PlainTextResponse(content=report.to_csv(), media_type="text/csv")
