"""add_road_type_and_pedestrian_phase

Revision ID: 20260528_0003
Revises: 20260528_0002
Create Date: 2026-05-28
"""
from typing import Sequence, Union

from alembic import op

revision: str = "20260528_0003"
down_revision: Union[str, None] = "20260528_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE intersections
        ADD COLUMN IF NOT EXISTS road_type VARCHAR(20) NOT NULL DEFAULT 'urban'
        CHECK (road_type IN ('urban','highway','service'))
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE intersections DROP COLUMN IF EXISTS road_type")
