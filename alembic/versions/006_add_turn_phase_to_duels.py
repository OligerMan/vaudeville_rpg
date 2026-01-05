"""Add turn_phase column to duels table.

Revision ID: 006
Revises: 005
Create Date: 2026-01-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create turn_phase enum
    turn_phase_enum = sa.Enum(
        "not_started", "pre_move_complete", "combat_complete", name="turn_phase"
    )
    turn_phase_enum.create(op.get_bind(), checkfirst=True)

    # Add current_phase column to duels table
    op.add_column(
        "duels",
        sa.Column(
            "current_phase",
            turn_phase_enum,
            nullable=False,
            server_default="not_started",
        ),
    )


def downgrade() -> None:
    op.drop_column("duels", "current_phase")

    # Drop enum
    sa.Enum(name="turn_phase").drop(op.get_bind(), checkfirst=True)
