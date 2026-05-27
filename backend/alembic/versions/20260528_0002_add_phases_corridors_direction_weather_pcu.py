"""add_phases_corridors_direction_weather_pcu

Revision ID: 20260528_0002
Revises: 20260528_0001
Create Date: 2026-05-28
"""
from typing import Sequence, Union

from alembic import op

revision: str = "20260528_0002"
down_revision: Union[str, None] = "20260528_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE traffic_observations
        ADD COLUMN IF NOT EXISTS direction VARCHAR(10) DEFAULT 'ALL'
        CHECK (direction IN ('N','S','E','W','NE','NW','SE','SW','ALL'))
        """
    )
    op.execute(
        """
        ALTER TABLE traffic_observations
        ADD COLUMN IF NOT EXISTS weather_condition VARCHAR(20) NOT NULL DEFAULT 'clear'
        """
    )
    op.execute(
        """
        ALTER TABLE traffic_observations
        ADD COLUMN IF NOT EXISTS pcu_total DOUBLE PRECISION
        """
    )
    op.execute("UPDATE traffic_observations SET direction = 'ALL' WHERE direction IS NULL")
    op.execute("UPDATE traffic_observations SET weather_condition = 'clear' WHERE weather_condition IS NULL")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS signal_phases (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            plan_id UUID NOT NULL REFERENCES signal_plans(id) ON DELETE CASCADE,
            phase_number INTEGER NOT NULL CHECK (phase_number >= 1),
            direction VARCHAR(10) NOT NULL CHECK (direction IN ('N','S','E','W','NE','NW','SE','SW','PED','ALL')),
            green_seconds INTEGER NOT NULL CHECK (green_seconds > 0),
            yellow_seconds INTEGER NOT NULL DEFAULT 4,
            phase_order INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_signal_phases_plan ON signal_phases(plan_id, phase_order)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS emergency_corridors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            emergency_id UUID NOT NULL REFERENCES emergency_events(id) ON DELETE CASCADE,
            intersection_id UUID NOT NULL REFERENCES intersections(id) ON DELETE CASCADE,
            sequence_order INTEGER NOT NULL,
            green_offset_seconds INTEGER NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_corridors_emergency ON emergency_corridors(emergency_id, sequence_order)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS emergency_corridors")
    op.execute("DROP TABLE IF EXISTS signal_phases")
    op.execute("ALTER TABLE traffic_observations DROP COLUMN IF EXISTS pcu_total")
    op.execute("ALTER TABLE traffic_observations DROP COLUMN IF EXISTS weather_condition")
    op.execute("ALTER TABLE traffic_observations DROP COLUMN IF EXISTS direction")
