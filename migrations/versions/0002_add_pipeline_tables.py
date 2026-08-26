"""add detection/target/classification/gis/risk/priority/mission/job/experiment tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-26

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "detections",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("survey_id", sa.String(length=36), sa.ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("mask_path", sa.String(length=1024), nullable=True),
        sa.Column("class_name", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("inference_time_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_detections_survey_id", "detections", ["survey_id"])

    op.create_table(
        "targets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("survey_id", sa.String(length=36), sa.ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False),
        sa.Column("detection_id", sa.String(length=36), sa.ForeignKey("detections.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "classification",
            sa.Enum("NATURAL_SEABED", "ANTHROPOGENIC", "UNCERTAIN", name="target_class", native_enum=False, length=32),
            nullable=True,
        ),
        sa.Column("debris_subclass", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("uncertainty", sa.Float(), nullable=True),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("mask_path", sa.String(length=1024), nullable=True),
        sa.Column("estimated_area_m2", sa.Float(), nullable=True),
        sa.Column("estimated_length_m", sa.Float(), nullable=True),
        sa.Column("estimated_width_m", sa.Float(), nullable=True),
        sa.Column("depth_m", sa.Float(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column(
            "coordinate_source",
            sa.Enum("GPS", "SONAR_METADATA", "SURVEY_TRANSFORM", "SIMULATED", name="coordinate_source", native_enum=False, length=32),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_targets_survey_id", "targets", ["survey_id"])

    op.create_table(
        "feature_vectors",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("target_id", sa.String(length=36), sa.ForeignKey("targets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature_version", sa.String(length=64), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("feature_names", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_feature_vectors_target_id", "feature_vectors", ["target_id"])

    op.create_table(
        "classification_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("target_id", sa.String(length=36), sa.ForeignKey("targets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature_vector_id", sa.String(length=36), sa.ForeignKey("feature_vectors.id", ondelete="SET NULL"), nullable=True),
        sa.Column("stage", sa.Enum("CLASSICAL", "QUANTUM", name="model_stage", native_enum=False, length=16), nullable=False),
        sa.Column(
            "run_status",
            sa.Enum("OK", "NOT_TRAINED", "UNAVAILABLE", "TEST_FIXTURE", name="model_run_status", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("predicted_class", sa.String(length=64), nullable=True),
        sa.Column("probabilities", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("feature_version", sa.String(length=64), nullable=True),
        sa.Column("inference_time_ms", sa.Float(), nullable=True),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_classification_records_target_id", "classification_records", ["target_id"])

    op.create_table(
        "environment_contexts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("target_id", sa.String(length=36), sa.ForeignKey("targets.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("reef_status", sa.Enum("OK", "NOT_CONFIGURED", "TEST_FIXTURE", name="reef_status", native_enum=False, length=32), nullable=False),
        sa.Column("reef_id", sa.String(length=128), nullable=True),
        sa.Column("reef_distance_m", sa.Float(), nullable=True),
        sa.Column("inside_reef", sa.Boolean(), nullable=True),
        sa.Column("habitat_context", sa.String(length=256), nullable=True),
        sa.Column("mpa_status", sa.Enum("OK", "NOT_CONFIGURED", "TEST_FIXTURE", name="mpa_status", native_enum=False, length=32), nullable=False),
        sa.Column("mpa_id", sa.String(length=128), nullable=True),
        sa.Column("mpa_name", sa.String(length=256), nullable=True),
        sa.Column("mpa_distance_m", sa.Float(), nullable=True),
        sa.Column("inside_mpa", sa.Boolean(), nullable=True),
        sa.Column("protection_context", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_environment_contexts_target_id", "environment_contexts", ["target_id"])

    op.create_table(
        "risk_scores",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("target_id", sa.String(length=36), sa.ForeignKey("targets.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("level", sa.Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="risk_level", native_enum=False, length=16), nullable=False),
        sa.Column("factors", sa.JSON(), nullable=False),
        sa.Column("weights_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_risk_scores_target_id", "risk_scores", ["target_id"])

    op.create_table(
        "priority_scores",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("target_id", sa.String(length=36), sa.ForeignKey("targets.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("action", sa.Enum("VERIFY_NOW", "VERIFY_NEXT", "VERIFY_LATER", "IGNORE", name="priority_action", native_enum=False, length=16), nullable=False),
        sa.Column(
            "recommended_method",
            sa.Enum("ROV_CAMERA", "AUV_OPTICAL", "DIVER", "MANUAL_REVIEW", "NONE", name="verification_method", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column("verification_required", sa.Boolean(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_priority_scores_target_id", "priority_scores", ["target_id"])

    op.create_table(
        "missions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("survey_id", sa.String(length=36), sa.ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Enum("DRAFT", "READY", "EXPORTED", "COMPLETED", name="mission_status", native_enum=False, length=16), nullable=False, server_default="DRAFT"),
        sa.Column("start_latitude", sa.Float(), nullable=True),
        sa.Column("start_longitude", sa.Float(), nullable=True),
        sa.Column("total_distance_m", sa.Float(), nullable=True),
        sa.Column("estimated_duration_s", sa.Float(), nullable=True),
        sa.Column("vehicle_speed_mps", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_missions_survey_id", "missions", ["survey_id"])

    op.create_table(
        "mission_targets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("mission_id", sa.String(length=36), sa.ForeignKey("missions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_id", sa.String(length=36), sa.ForeignKey("targets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("distance_from_previous_m", sa.Float(), nullable=True),
        sa.Column("cumulative_distance_m", sa.Float(), nullable=True),
    )
    op.create_index("ix_mission_targets_mission_id", "mission_targets", ["mission_id"])
    op.create_index("ix_mission_targets_target_id", "mission_targets", ["target_id"])

    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("survey_id", sa.String(length=36), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED", "VALIDATING", "PREPROCESSING", "DETECTING", "CLASSIFYING", "QML_CLASSIFYING",
                "GEOLOCATING", "GIS_ENRICHMENT", "RISK_SCORING", "PRIORITIZING", "MISSION_PLANNING",
                "REPORTING", "COMPLETED", "FAILED",
                name="processing_job_status", native_enum=False, length=32,
            ),
            nullable=False,
            server_default="QUEUED",
        ),
        sa.Column("error_message", sa.String(length=2048), nullable=True),
        sa.Column("stage_log", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_processing_jobs_survey_id", "processing_jobs", ["survey_id"])

    op.create_table(
        "experiments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("dataset_version", sa.String(length=64), nullable=False),
        sa.Column("feature_version", sa.String(length=64), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("classical_status", sa.String(length=16), nullable=False),
        sa.Column("classical_metrics", sa.JSON(), nullable=True),
        sa.Column("quantum_status", sa.String(length=16), nullable=False),
        sa.Column("quantum_metrics", sa.JSON(), nullable=True),
        sa.Column("notes", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("experiments")
    op.drop_index("ix_processing_jobs_survey_id", table_name="processing_jobs")
    op.drop_table("processing_jobs")
    op.drop_index("ix_mission_targets_target_id", table_name="mission_targets")
    op.drop_index("ix_mission_targets_mission_id", table_name="mission_targets")
    op.drop_table("mission_targets")
    op.drop_index("ix_missions_survey_id", table_name="missions")
    op.drop_table("missions")
    op.drop_index("ix_priority_scores_target_id", table_name="priority_scores")
    op.drop_table("priority_scores")
    op.drop_index("ix_risk_scores_target_id", table_name="risk_scores")
    op.drop_table("risk_scores")
    op.drop_index("ix_environment_contexts_target_id", table_name="environment_contexts")
    op.drop_table("environment_contexts")
    op.drop_index("ix_classification_records_target_id", table_name="classification_records")
    op.drop_table("classification_records")
    op.drop_index("ix_feature_vectors_target_id", table_name="feature_vectors")
    op.drop_table("feature_vectors")
    op.drop_index("ix_targets_survey_id", table_name="targets")
    op.drop_table("targets")
    op.drop_index("ix_detections_survey_id", table_name="detections")
    op.drop_table("detections")
