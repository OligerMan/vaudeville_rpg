"""Add pending_generations table for admin state persistence.

Revision ID: 007
Revises: 006
Create Date: 2026-01-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pending_generations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pending_generations_chat_id",
        "pending_generations",
        ["chat_id"],
        unique=True,
    )
    op.create_index(
        "ix_pending_generations_user_id",
        "pending_generations",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pending_generations_user_id", table_name="pending_generations")
    op.drop_index("ix_pending_generations_chat_id", table_name="pending_generations")
    op.drop_table("pending_generations")
