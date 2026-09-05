"""add_metrics_detail_to_model_evaluations

Adds a nullable JSON column ``metrics_detail`` to ``model_evaluations`` to store
per-target (density / vehicle_count) metrics and walk-forward validation
summaries. The existing mae/rmse/r2 columns are kept as coarse summary fields
for backward compatibility with existing API/UI consumers.

Revision ID: 20260905_0006
Revises: 20260530_0005
Create Date: 2026-09-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260905_0006"
down_revision: Union[str, None] = "20260530_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "model_evaluations",
        sa.Column("metrics_detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("model_evaluations", "metrics_detail")
