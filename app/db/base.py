"""
Import every ORM model here.

Alembic's `env.py` imports `Base.metadata` from this module. Any model
that isn't imported below will silently be invisible to
`alembic revision --autogenerate`, so every new model module must be
added to this list.
"""

from app.db.database import Base  # noqa: F401
from app.models.classification import ClassificationRecord  # noqa: F401
from app.models.detection import Detection  # noqa: F401
from app.models.environment import EnvironmentContext  # noqa: F401
from app.models.experiment import Experiment  # noqa: F401
from app.models.feature_vector import FeatureVector  # noqa: F401
from app.models.mission import Mission, MissionTarget  # noqa: F401
from app.models.priority import PriorityScore  # noqa: F401
from app.models.processing_job import ProcessingJob  # noqa: F401
from app.models.risk import RiskScore  # noqa: F401
from app.models.survey import Survey  # noqa: F401
from app.models.target import Target  # noqa: F401

__all__ = [
    "Base",
    "Survey",
    "Detection",
    "Target",
    "FeatureVector",
    "ClassificationRecord",
    "EnvironmentContext",
    "RiskScore",
    "PriorityScore",
    "Mission",
    "MissionTarget",
    "ProcessingJob",
    "Experiment",
]
