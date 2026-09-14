"""add execution reported at

Revision ID: e5c1e605dfd1
Revises: 98137cc75568
Create Date: 2026-09-14 11:26:06.350122
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5c1e605dfd1'
down_revision: Union[str, None] = '98137cc75568'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "signal_control_commands",
        sa.Column(
            "execution_reported_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column(
        "signal_control_commands",
        "execution_reported_at",
    )
