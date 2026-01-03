"""Add duel system tables.

Revision ID: 004
Revises: 003
Create Date: 2026-01-03

Adds Duel, DuelParticipant, and DuelAction tables for the duel engine.
Also adds is_bot flag to players and updates player_combat_states with
proper foreign key to duels.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============================================
    # Add is_bot flag to players table
    # ============================================
    op.add_column(
        "players",
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default="false"),
    )

    # ============================================
    # Create duel_status enum
    # ============================================
    duel_status_enum = sa.Enum(
        "pending",
        "in_progress",
        "completed",
        "cancelled",
        name="duel_status",
    )
    duel_status_enum.create(op.get_bind(), checkfirst=True)

    # ============================================
    # Create duel_action_type enum
    # ============================================
    duel_action_type_enum = sa.Enum(
        "attack",
        "defense",
        "misc",
        "skip",
        name="duel_action_type",
    )
    duel_action_type_enum.create(op.get_bind(), checkfirst=True)

    # ============================================
    # Create duels table
    # ============================================
    op.create_table(
        "duels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "setting_id", sa.Integer(), sa.ForeignKey("settings.id"), nullable=False, index=True
        ),
        sa.Column("status", duel_status_enum, nullable=False, server_default="pending"),
        sa.Column("current_turn", sa.Integer(), nullable=False, server_default="1"),
        # winner_participant_id added later after duel_participants exists
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
    )

    # ============================================
    # Create duel_participants table
    # ============================================
    op.create_table(
        "duel_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "duel_id", sa.Integer(), sa.ForeignKey("duels.id"), nullable=False, index=True
        ),
        sa.Column(
            "player_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False, index=True
        ),
        sa.Column("turn_order", sa.Integer(), nullable=False),
        sa.Column("is_ready", sa.Boolean(), nullable=False, server_default="false"),
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
    )

    # ============================================
    # Add winner_participant_id to duels (now that duel_participants exists)
    # ============================================
    op.add_column(
        "duels",
        sa.Column(
            "winner_participant_id",
            sa.Integer(),
            sa.ForeignKey("duel_participants.id"),
            nullable=True,
        ),
    )

    # ============================================
    # Create duel_actions table
    # ============================================
    op.create_table(
        "duel_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "duel_id", sa.Integer(), sa.ForeignKey("duels.id"), nullable=False, index=True
        ),
        sa.Column(
            "participant_id",
            sa.Integer(),
            sa.ForeignKey("duel_participants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("action_type", duel_action_type_enum, nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id"), nullable=True),
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
    )

    # ============================================
    # Update player_combat_states to have proper FK to duels
    # First drop the old constraint, then add the new FK
    # ============================================
    # Drop the old unique constraint
    op.drop_constraint("uq_combat_state_player_duel", "player_combat_states", type_="unique")

    # Make duel_id NOT NULL and add FK
    op.alter_column(
        "player_combat_states",
        "duel_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_combat_state_duel",
        "player_combat_states",
        "duels",
        ["duel_id"],
        ["id"],
    )

    # Recreate the unique constraint
    op.create_unique_constraint(
        "uq_combat_state_player_duel",
        "player_combat_states",
        ["player_id", "duel_id"],
    )


def downgrade() -> None:
    # Drop FK and restore nullable duel_id
    op.drop_constraint("uq_combat_state_player_duel", "player_combat_states", type_="unique")
    op.drop_constraint("fk_combat_state_duel", "player_combat_states", type_="foreignkey")
    op.alter_column(
        "player_combat_states",
        "duel_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.create_unique_constraint(
        "uq_combat_state_player_duel",
        "player_combat_states",
        ["player_id", "duel_id"],
    )

    # Drop tables
    op.drop_table("duel_actions")
    op.drop_column("duels", "winner_participant_id")
    op.drop_table("duel_participants")
    op.drop_table("duels")

    # Drop enums
    sa.Enum(name="duel_action_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="duel_status").drop(op.get_bind(), checkfirst=True)

    # Drop is_bot column
    op.drop_column("players", "is_bot")
