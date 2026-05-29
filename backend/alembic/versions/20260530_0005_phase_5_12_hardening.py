"""phase_5_12_hardening

Revision ID: 20260530_0005
Revises: 20260530_0004
Create Date: 2026-05-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260530_0005"
down_revision: Union[str, None] = "20260530_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "signal_plans",
        sa.Column("decision_source", sa.String(length=40), nullable=False, server_default="historical_observation"),
    )
    op.alter_column("signal_plans", "decision_source", server_default=None)

    op.create_table(
        "intersection_signal_states",
        sa.Column(
            "intersection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("intersections.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("last_density", sa.Float(), nullable=False, server_default="0"),
        sa.Column("last_vehicle_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "last_signal_plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("signal_plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("last_detection_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_source", sa.String(length=40), nullable=False, server_default="safe_fallback_plan"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_intersection_signal_states_updated_at",
        "intersection_signal_states",
        ["updated_at"],
    )

    op.create_table(
        "model_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("model_version", sa.String(length=80), nullable=False),
        sa.Column("model_type", sa.String(length=40), nullable=False),
        sa.Column("samples", sa.Integer(), nullable=False),
        sa.Column("mae", sa.Float(), nullable=True),
        sa.Column("rmse", sa.Float(), nullable=True),
        sa.Column("r2", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("model_version", name="uq_model_evaluations_model_version"),
    )
    op.create_index("ix_model_evaluations_created_at", "model_evaluations", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_model_evaluations_created_at", table_name="model_evaluations")
    op.drop_table("model_evaluations")
    op.drop_index("ix_intersection_signal_states_updated_at", table_name="intersection_signal_states")
    op.drop_table("intersection_signal_states")
    op.drop_column("signal_plans", "decision_source")
