"""create surveys table

Revision ID: 0001
Revises:
Create Date: 2026-08-26

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SURVEY_STATUS_VALUES = (
    "CREATED",
    "UPLOADED",
    "PREPROCESSING",
    "DETECTING",
    "CLASSIFYING",
    "ENRICHING",
    "SCORING",
    "COMPLETED",
    "FAILED",
)


def upgrade() -> None:
    # PostGIS is enabled up front even though Phase 5 doesn't yet store
    # any geometry columns -- later phases (Target, GIS providers) rely
    # on it being present, and enabling it here keeps a single source of
    # truth for schema setup instead of a second ad-hoc bootstrap step.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "surveys",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("file_type", sa.String(length=16), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("coordinate_reference_system", sa.String(length=64), nullable=True),
        sa.Column("origin_latitude", sa.Float(), nullable=True),
        sa.Column("origin_longitude", sa.Float(), nullable=True),
        sa.Column("meters_per_pixel", sa.Float(), nullable=True),
        sa.Column("depth_min", sa.Float(), nullable=True),
        sa.Column("depth_max", sa.Float(), nullable=True),
        sa.Column("sonar_frequency", sa.Float(), nullable=True),
        sa.Column("sensor_name", sa.String(length=128), nullable=True),
        sa.Column(
            "status",
            sa.Enum(*SURVEY_STATUS_VALUES, name="survey_status", native_enum=False, length=32),
            nullable=False,
            server_default="CREATED",
        ),
        sa.Column("failure_reason", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_surveys_status", "surveys", ["status"])
    op.create_index("ix_surveys_created_at", "surveys", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_surveys_created_at", table_name="surveys")
    op.drop_index("ix_surveys_status", table_name="surveys")
    op.drop_table("surveys")
