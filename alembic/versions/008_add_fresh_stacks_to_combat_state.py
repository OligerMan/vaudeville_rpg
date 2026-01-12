"""Add fresh_stacks column to player_combat_states table.

Fresh stacks track stacks added during the current turn.
These stacks are protected from passive decay (POST_MOVE phase)
but can still be removed by active abilities.

Revision ID: 008
Revises: 06eb078065ea
Create Date: 2026-01-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: str | None = "06eb078065ea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "player_combat_states",
        sa.Column(
            "fresh_stacks",
            JSONB,
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("player_combat_states", "fresh_stacks")
