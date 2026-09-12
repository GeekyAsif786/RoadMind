"""add signal control commands

Revision ID: 98137cc75568
Revises: ed9cac1803b2
Create Date: 2026-09-08 12:27:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "98137cc75568"
down_revision: Union[str, None] = "ed9cac1803b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signal_control_commands",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "intersection_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "phase_number",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "acknowledged_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["intersection_id"],
            ["intersections.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["device_credentials.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["signal_plans.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_signal_control_commands_intersection_id",
        "signal_control_commands",
        ["intersection_id"],
        unique=False,
    )
    op.create_index(
        "ix_signal_control_commands_device_id",
        "signal_control_commands",
        ["device_id"],
        unique=False,
    )
    op.create_index(
        "ix_signal_control_commands_plan_id",
        "signal_control_commands",
        ["plan_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_signal_control_commands_plan_id",
        table_name="signal_control_commands",
    )
    op.drop_index(
        "ix_signal_control_commands_device_id",
        table_name="signal_control_commands",
    )
    op.drop_index(
        "ix_signal_control_commands_intersection_id",
        table_name="signal_control_commands",
    )
    op.drop_table("signal_control_commands")