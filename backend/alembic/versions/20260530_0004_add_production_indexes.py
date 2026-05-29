"""add_production_indexes

Revision ID: 20260530_0004
Revises: 20260528_0003
Create Date: 2026-05-30
"""
from typing import Sequence, Union

from alembic import op

revision: str = "20260530_0004"
down_revision: Union[str, None] = "20260528_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_traffic_observations_captured_at
        ON traffic_observations(captured_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_traffic_observations_intersection_direction_time
        ON traffic_observations(intersection_id, direction, captured_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_detection_events_intersection_created
        ON detection_events(intersection_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_predictions_intersection_created
        ON predictions(intersection_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_emergency_events_intersection_detected
        ON emergency_events(intersection_id, detected_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_emergency_corridors_intersection_status
        ON emergency_corridors(intersection_id, status)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_emergency_corridors_intersection_status")
    op.execute("DROP INDEX IF EXISTS ix_emergency_events_intersection_detected")
    op.execute("DROP INDEX IF EXISTS ix_predictions_intersection_created")
    op.execute("DROP INDEX IF EXISTS ix_detection_events_intersection_created")
    op.execute("DROP INDEX IF EXISTS ix_traffic_observations_intersection_direction_time")
    op.execute("DROP INDEX IF EXISTS ix_traffic_observations_captured_at")
