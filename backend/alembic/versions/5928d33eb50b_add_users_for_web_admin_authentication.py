"""add users for web admin authentication

Revision ID: 5928d33eb50b
Revises: 20260905_0006
Create Date: <KEEP_GENERATED_DATE>
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5928d33eb50b"
down_revision: Union[str, Sequence[str], None] = (
    "20260905_0006"
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "username",
            sa.String(length=80),
            nullable=False,
        ),
        sa.Column(
            "email",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "password_hash",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            server_default="viewer",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "email",
            name="uq_users_email",
        ),
        sa.UniqueConstraint(
            "username",
            name="uq_users_username",
        ),
    )

    op.create_index(
        "ix_users_username",
        "users",
        ["username"],
        unique=False,
    )

    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_users_email",
        table_name="users",
    )

    op.drop_index(
        "ix_users_username",
        table_name="users",
    )

    op.drop_table("users")