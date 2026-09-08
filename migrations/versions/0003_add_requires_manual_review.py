"""add requires_manual_review to detections/targets

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-08

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("detections", sa.Column("requires_manual_review", sa.Boolean(), nullable=True))
    op.add_column("targets", sa.Column("requires_manual_review", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("targets", "requires_manual_review")
    op.drop_column("detections", "requires_manual_review")
