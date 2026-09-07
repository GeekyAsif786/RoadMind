"""add device credentials

Revision ID: 0398e0c85365
Revises: 5928d33eb50b
Create Date: 2026-09-07 10:07:24.177203
"""
from sqlalchemy.dialects import postgresql
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0398e0c85365"
down_revision: Union[str, Sequence[str], None] = "5928d33eb50b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_credentials",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "intersection_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "name",
            sa.String(length=120),
            nullable=False,
        ),
        sa.Column(
            "credential_hash",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "scopes",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_used_at",
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "name",
            name="uq_device_credentials_name",
        ),
    )

    op.create_index(
        "ix_device_credentials_intersection_id",
        "device_credentials",
        ["intersection_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_device_credentials_intersection_id",
        table_name="device_credentials",
    )

    op.drop_table("device_credentials")