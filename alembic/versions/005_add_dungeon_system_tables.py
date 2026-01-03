"""Add dungeon system tables.

Revision ID: 005
Revises: 004
Create Date: 2026-01-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create dungeon_difficulty enum
    dungeon_difficulty_enum = sa.Enum(
        "easy", "normal", "hard", "nightmare", name="dungeon_difficulty"
    )
    dungeon_difficulty_enum.create(op.get_bind(), checkfirst=True)

    # Create dungeon_status enum
    dungeon_status_enum = sa.Enum(
        "in_progress", "completed", "failed", "abandoned", name="dungeon_status"
    )
    dungeon_status_enum.create(op.get_bind(), checkfirst=True)

    # Create dungeons table
    op.create_table(
        "dungeons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("setting_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "difficulty",
            dungeon_difficulty_enum,
            nullable=False,
            server_default="normal",
        ),
        sa.Column("total_stages", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("current_stage", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "status",
            dungeon_status_enum,
            nullable=False,
            server_default="in_progress",
        ),
        sa.Column("current_duel_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.ForeignKeyConstraint(["setting_id"], ["settings.id"]),
        sa.ForeignKeyConstraint(["current_duel_id"], ["duels.id"]),
    )
    op.create_index("ix_dungeons_player_id", "dungeons", ["player_id"])
    op.create_index("ix_dungeons_setting_id", "dungeons", ["setting_id"])

    # Create dungeon_enemies table
    op.create_table(
        "dungeon_enemies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dungeon_id", sa.Integer(), nullable=False),
        sa.Column("stage", sa.Integer(), nullable=False),
        sa.Column("enemy_player_id", sa.Integer(), nullable=False),
        sa.Column("defeated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["dungeon_id"], ["dungeons.id"]),
        sa.ForeignKeyConstraint(["enemy_player_id"], ["players.id"]),
    )
    op.create_index("ix_dungeon_enemies_dungeon_id", "dungeon_enemies", ["dungeon_id"])


def downgrade() -> None:
    op.drop_index("ix_dungeon_enemies_dungeon_id", "dungeon_enemies")
    op.drop_table("dungeon_enemies")

    op.drop_index("ix_dungeons_setting_id", "dungeons")
    op.drop_index("ix_dungeons_player_id", "dungeons")
    op.drop_table("dungeons")

    # Drop enums
    sa.Enum(name="dungeon_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="dungeon_difficulty").drop(op.get_bind(), checkfirst=True)
