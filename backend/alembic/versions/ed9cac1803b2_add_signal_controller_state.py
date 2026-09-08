"""add signal controller state

Revision ID: ed9cac1803b2
Revises: e6aef36576f6
Create Date: 2026-09-08 11:27:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "ed9cac1803b2"
down_revision: Union[str, None] = "e6aef36576f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signal_controller_states",
        sa.Column("intersection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_phase", sa.Integer(), nullable=False),
        sa.Column("phase_state", sa.String(length=20), nullable=False),
        sa.Column("controller_status", sa.String(length=20), nullable=False),
        sa.Column("reported_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("phase_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["intersection_id"],
            ["intersections.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reported_plan_id"],
            ["signal_plans.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("intersection_id"),
    )


def downgrade() -> None:
    op.drop_table("signal_controller_states")