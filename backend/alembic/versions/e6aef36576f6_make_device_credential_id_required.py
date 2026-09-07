"""make device credential id required

Revision ID: e6aef36576f6
Revises: b07849a4862e
Create Date: 2026-09-07 10:38:19.638064
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e6aef36576f6"
down_revision: Union[str, Sequence[str], None] = "b07849a4862e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "device_credentials",
        "credential_id",
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "device_credentials",
        "credential_id",
        nullable=True,
    )