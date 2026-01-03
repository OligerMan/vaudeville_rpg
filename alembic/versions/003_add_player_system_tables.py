"""Add player system tables.

Revision ID: 003
Revises: 002
Create Date: 2026-01-03

Adds Player and PlayerCombatState tables for the player system.
Players are per-chat with equipped items and PvP rating.
Combat state is persisted to survive bot restarts.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============================================
    # Create players table
    # ============================================
    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column(
            "setting_id", sa.Integer(), sa.ForeignKey("settings.id"), nullable=False, index=True
        ),
        sa.Column("display_name", sa.String(100), nullable=False),
        # Base stats
        sa.Column("max_hp", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("max_special_points", sa.Integer(), nullable=False, server_default="50"),
        # PvP rating
        sa.Column("rating", sa.Integer(), nullable=False, server_default="1000"),
        # Equipped items (nullable = no item equipped)
        sa.Column(
            "attack_item_id",
            sa.Integer(),
            sa.ForeignKey("items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "defense_item_id",
            sa.Integer(),
            sa.ForeignKey("items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "misc_item_id",
            sa.Integer(),
            sa.ForeignKey("items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Unique constraint: one player per user per setting
        sa.UniqueConstraint("telegram_user_id", "setting_id", name="uq_player_user_setting"),
    )

    # ============================================
    # Create player_combat_states table
    # ============================================
    op.create_table(
        "player_combat_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "player_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False, index=True
        ),
        # duel_id will reference the duels table when implemented
        sa.Column("duel_id", sa.Integer(), nullable=True, index=True),
        # Current stats
        sa.Column("current_hp", sa.Integer(), nullable=False),
        sa.Column("current_special_points", sa.Integer(), nullable=False),
        # Current attribute stacks (JSONB for flexibility)
        sa.Column("attribute_stacks", JSONB(), nullable=False, server_default="{}"),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Unique constraint: one state per player per duel
        sa.UniqueConstraint("player_id", "duel_id", name="uq_combat_state_player_duel"),
    )


def downgrade() -> None:
    op.drop_table("player_combat_states")
    op.drop_table("players")