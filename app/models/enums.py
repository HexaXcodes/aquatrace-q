"""
Shared enums.

Kept in one module (rather than inside `models/survey.py`) so that
schemas, services, and later phases (detections, targets, missions) can
import them without creating circular imports with the ORM layer.
"""

from __future__ import annotations

import enum


class SurveyStatus(str, enum.Enum):
    """
    Lifecycle of a survey as it moves through the processing pipeline.

    Only CREATED, UPLOADED, and FAILED are reachable in Phases 1-5.
    The remaining values exist now so the column doesn't need a migration
    every time a later phase adds a pipeline stage.
    """

    CREATED = "CREATED"
    UPLOADED = "UPLOADED"
    PREPROCESSING = "PREPROCESSING"
    DETECTING = "DETECTING"
    CLASSIFYING = "CLASSIFYING"
    ENRICHING = "ENRICHING"
    SCORING = "SCORING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CoordinateSource(str, enum.Enum):
    """Provenance of a lat/lon pair, so simulated coordinates are never
    confused with real ones downstream (see spec section 19)."""

    GPS = "GPS"
    SONAR_METADATA = "SONAR_METADATA"
    SURVEY_TRANSFORM = "SURVEY_TRANSFORM"
    SIMULATED = "SIMULATED"


class TargetClass(str, enum.Enum):
    """Top-level classification bucket. Kept small and stable; the
    interesting detail lives in `debris_subclass`, which is a plain
    string precisely so new subclasses never require a migration."""

    NATURAL_SEABED = "NATURAL_SEABED"
    ANTHROPOGENIC = "ANTHROPOGENIC"
    UNCERTAIN = "UNCERTAIN"


# Known anthropogenic subclasses. This is a vocabulary, not a constraint --
# `Target.debris_subclass` and `ClassificationRecord.predicted_subclass`
# are plain strings so a model can emit a class outside this list (it will
# just be new information, not a validation failure). Kept here purely so
# the frontend / docs have a canonical list to render against.
#
# Mixed granularity is deliberate, not an oversight: ghost_net/crab_pot/
# pipe/metal_debris/shipwreck/other_debris are fine-grained (from
# detectors purpose-built for one specific class, e.g. E004's
# "shipwreck"), while marine_debris/gear_hardware/other_anthropogenic are
# the coarser 3-class taxonomy the general-purpose YOLO11s detector was
# actually trained on (see app/ml/yolo_debris_detector.py,
# YOLO_TrainedModel/model_contract.json). Reporting exactly what each
# detector said, at whatever granularity it actually operates at, is
# preferred over inventing a lossy mapping between the two vocabularies
# just to make them look uniform -- see docs/ml-integration.md.
KNOWN_DEBRIS_SUBCLASSES: tuple[str, ...] = (
    "ghost_net",
    "crab_pot",
    "pipe",
    "metal_debris",
    "shipwreck",
    "rock",
    "other_debris",
    "marine_debris",
    "gear_hardware",
    "other_anthropogenic",
    "natural_seabed",
    "unknown",
)


class UncertaintyLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ModelStage(str, enum.Enum):
    """Which stage produced a ClassificationRecord."""

    CLASSICAL = "CLASSICAL"
    QUANTUM = "QUANTUM"


class ModelRunStatus(str, enum.Enum):
    """Did this classification stage actually run a trained model?

    `NOT_TRAINED` / `UNAVAILABLE` are legitimate, honestly-reported
    outcomes -- never silently replaced with a fabricated prediction.
    """

    OK = "OK"
    NOT_TRAINED = "NOT_TRAINED"
    UNAVAILABLE = "UNAVAILABLE"
    TEST_FIXTURE = "TEST_FIXTURE"


class GISStatus(str, enum.Enum):
    OK = "OK"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    TEST_FIXTURE = "TEST_FIXTURE"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PriorityAction(str, enum.Enum):
    VERIFY_NOW = "VERIFY_NOW"
    VERIFY_NEXT = "VERIFY_NEXT"
    VERIFY_LATER = "VERIFY_LATER"
    IGNORE = "IGNORE"


class VerificationMethod(str, enum.Enum):
    ROV_CAMERA = "ROV_CAMERA"
    AUV_OPTICAL = "AUV_OPTICAL"
    DIVER = "DIVER"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    NONE = "NONE"


class MissionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    EXPORTED = "EXPORTED"
    COMPLETED = "COMPLETED"


class ProcessingJobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    PREPROCESSING = "PREPROCESSING"
    DETECTING = "DETECTING"
    CLASSIFYING = "CLASSIFYING"
    QML_CLASSIFYING = "QML_CLASSIFYING"
    GEOLOCATING = "GEOLOCATING"
    GIS_ENRICHMENT = "GIS_ENRICHMENT"
    RISK_SCORING = "RISK_SCORING"
    PRIORITIZING = "PRIORITIZING"
    MISSION_PLANNING = "MISSION_PLANNING"
    REPORTING = "REPORTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Ordered so services can compute "is stage A before stage B" if ever needed.
PROCESSING_STAGE_ORDER: tuple[ProcessingJobStatus, ...] = (
    ProcessingJobStatus.QUEUED,
    ProcessingJobStatus.VALIDATING,
    ProcessingJobStatus.PREPROCESSING,
    ProcessingJobStatus.DETECTING,
    ProcessingJobStatus.CLASSIFYING,
    ProcessingJobStatus.QML_CLASSIFYING,
    ProcessingJobStatus.GEOLOCATING,
    ProcessingJobStatus.GIS_ENRICHMENT,
    ProcessingJobStatus.RISK_SCORING,
    ProcessingJobStatus.PRIORITIZING,
    ProcessingJobStatus.MISSION_PLANNING,
    ProcessingJobStatus.REPORTING,
    ProcessingJobStatus.COMPLETED,
)
