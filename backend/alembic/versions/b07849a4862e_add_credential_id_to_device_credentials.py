"""add credential id to device credentials

Revision ID: b07849a4862e
Revises: 0398e0c85365
Create Date: 2026-09-07 10:29:46.417293
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b07849a4862e"
down_revision: Union[str, Sequence[str], None] = "0398e0c85365"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "device_credentials",
        sa.Column(
            "credential_id",
            sa.String(length=32),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_device_credentials_credential_id",
        "device_credentials",
        ["credential_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_device_credentials_credential_id",
        table_name="device_credentials",
    )

    op.drop_column(
        "device_credentials",
        "credential_id",
    )