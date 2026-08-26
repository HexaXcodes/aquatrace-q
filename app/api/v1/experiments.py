"""Experiment endpoints (Phase 9/20): POST /experiments/classification, GET /experiments/{id}"""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import AquaTraceError
from app.db.session import get_db
from app.schemas.experiment import ExperimentRead, ExperimentRequest
from app.services import experiment_service

router = APIRouter(prefix="/experiments", tags=["experiments"])


class InvalidExperimentRequestError(AquaTraceError):
    status_code = 400


@router.post(
    "/classification",
    response_model=ExperimentRead,
    status_code=201,
    summary="Run a classical-vs-quantum classification comparison on a supplied labelled dataset",
)
def run_classification_experiment(payload: ExperimentRequest, db: Session = Depends(get_db)) -> ExperimentRead:
    X = np.array([s.features for s in payload.samples], dtype=np.float64)
    y = [s.label for s in payload.samples]

    try:
        experiment = experiment_service.run_classification_experiment(
            db,
            X,
            y,
            dataset_version=payload.dataset_version,
            feature_version=payload.feature_version,
            test_size=payload.test_size,
        )
    except ValueError as exc:
        raise InvalidExperimentRequestError(str(exc)) from exc

    return ExperimentRead.model_validate(experiment)


@router.get("/{experiment_id}", response_model=ExperimentRead, summary="Get an experiment result")
def get_experiment(experiment_id: str, db: Session = Depends(get_db)) -> ExperimentRead:
    experiment = experiment_service.get_experiment(db, experiment_id)
    return ExperimentRead.model_validate(experiment)
